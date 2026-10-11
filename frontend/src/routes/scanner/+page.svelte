<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { createWorker } from 'tesseract.js';
  import { MAT_COLUMNS, MAT_ROWS, MAT_WIDTH_CM, MAT_HEIGHT_CM, cellAtMatPoint, slotsForZone } from '$lib/config/board';
  import {
    cameraFetch,
    clearCameraToken,
    getCameraToken,
    loadCameraBoardCards,
    loadCameraSession,
    redeemCameraPairing,
    saveCameraToken,
    type CameraDeckCard,
    type CameraBoardCard,
    type CameraSession
  } from '$lib/services/camera';

  interface Point { x: number; y: number }
  interface AprilDetection { id: number; family: string; center: Point; corners: Point[]; hamming: number }
  interface AprilDetectionBatch { detections: AprilDetection[]; processingTime: number }
  interface AprilTagManager {
    initialize(): Promise<void>;
    setupDetector(family: string, hamming: number, params?: Record<string, number | boolean>): Promise<void>;
    detect(image: ImageData, width: number, height: number): Promise<AprilDetectionBatch>;
    terminate(): void;
  }
  interface AprilTagWindow extends Window {
    AprilTagDetectorManager?: new () => AprilTagManager;
  }
  interface Suggestion { card: CameraDeckCard; score: number }

  const zones = [
    { value: 'monster_zone', label: 'Zona de monstruos' },
    { value: 'spell_trap_zone', label: 'Mágicas y trampas' },
    { value: 'extra_monster', label: 'Monstruo extra' },
    { value: 'pendulum', label: 'Péndulo' },
    { value: 'field_spell', label: 'Campo' },
    { value: 'graveyard', label: 'Cementerio' },
    { value: 'banished', label: 'Destierro' },
    { value: 'hand', label: 'Mano' },
    { value: 'extra_deck', label: 'Deck extra' },
    { value: 'main_deck', label: 'Deck principal' }
  ].map((zone) => ({ ...zone, slots: slotsForZone(zone.value) }));
  const markerIds = [0, 1, 2, 4];
  const markerNames: Record<number, string> = { 0: 'superior izquierda', 1: 'superior derecha', 2: 'inferior izquierda', 4: 'inferior derecha' };

  let session: CameraSession | null = null;
  let boardCards: CameraBoardCard[] = [];
  let videoElement: HTMLVideoElement;
  let processCanvas: HTMLCanvasElement;
  let overlayCanvas: HTMLCanvasElement;
  let stream: MediaStream | null = null;
  let detector: AprilTagManager | null = null;
  let ocrWorker: Awaited<ReturnType<typeof createWorker>> | null = null;
  let animationFrame = 0;
  let isLoading = true;
  let isCameraStarting = false;
  let isCapturing = false;
  let isRecognizing = false;
  let isSubmitting = false;
  let cameraError = '';
  let pageError = '';
  let captureMessage = '';
  let cameraStatus = 'Preparando sesión…';
  let markerCount = 0;
  let missingMarkerNames = Object.values(markerNames);
  let calibration: number[] | null = null;
  let capturedCalibration: number[] | null = null;
  let capturePanelElement: HTMLElement;
  let capturedImage = '';
  let captureCanvas: HTMLCanvasElement | null = null;
  let captureId = '';
  let ocrText = '';
  let suggestions: Suggestion[] = [];
  let selectedCardId = '';
  let selectedZone = 'monster_zone';
  let selectedPosition = 1;
  let faceDown = false;
  let useCurrentCanvas = false;
  let autoCapture = true;
  let stableFrames = 0;
  let previousCenters: Map<number, Point> | null = null;
  let lastAutoCaptureAt = 0;
  let lastAutoCellKey = '';
  const AUTO_STABLE_FRAMES = 4;
  const AUTO_MOVE_TOLERANCE_PX = 6;
  const AUTO_COOLDOWN_MS = 4000;
  const AUTO_CONFIRM_MAX_SCORE = 0.15;

  $: selectedZoneDefinition = zones.find((zone) => zone.value === selectedZone) || zones[0];
  $: availablePositions = availablePositionsForZone(selectedZone);
  $: isCalibrated = calibration !== null;

  onMount(() => {
    let disposed = false;

    async function initialize() {
      try {
        const pairingToken = new URLSearchParams(window.location.search).get('pairing_token');
        if (pairingToken) {
          const paired = await redeemCameraPairing(pairingToken);
          if (disposed) return;
          saveCameraToken(paired.camera_token);
          session = paired;
          window.history.replaceState(null, '', '/scanner');
        } else if (getCameraToken()) {
          session = await loadCameraSession();
        } else {
          pageError = 'Abre el QR de vinculación del tablero para autorizar este teléfono.';
          isLoading = false;
          return;
        }

        if (disposed) return;
        boardCards = await loadCameraBoardCards();
        selectedPosition = availablePositionsForZone(selectedZone)[0] || 0;
        await loadAprilTagDetector();
        if (disposed) return;
        await startCamera();
      } catch (error) {
        if (!disposed) {
          pageError = error instanceof Error ? error.message : 'No se pudo preparar el escáner.';
          if (getCameraToken()) clearCameraToken();
        }
      } finally {
        if (!disposed) isLoading = false;
      }
    }

    void initialize();

    return () => {
      disposed = true;
      stopCamera();
      detector?.terminate();
      if (ocrWorker) void ocrWorker.terminate();
      if (animationFrame) cancelAnimationFrame(animationFrame);
    };
  });

  async function loadClassicScript(src: string): Promise<void> {
    const existing = document.querySelector<HTMLScriptElement>(`script[data-apriltag="${src}"]`);
    if (existing?.dataset.loaded === 'true') return;
    if (existing) {
      await new Promise<void>((resolve, reject) => {
        existing.addEventListener('load', () => resolve(), { once: true });
        existing.addEventListener('error', () => reject(new Error('No se pudo cargar el detector AprilTag.')), { once: true });
      });
      return;
    }

    await new Promise<void>((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.dataset.apriltag = src;
      script.onload = () => {
        script.dataset.loaded = 'true';
        resolve();
      };
      script.onerror = () => reject(new Error('No se pudo cargar el detector AprilTag local.'));
      document.head.appendChild(script);
    });
  }

  async function loadAprilTagDetector() {
    await loadClassicScript('/vendor/apriltag-js/detector-manager.js');
    const DetectorManager = (window as AprilTagWindow).AprilTagDetectorManager;
    if (!DetectorManager) throw new Error('El detector AprilTag no quedó disponible en el navegador.');
    detector = new DetectorManager();
    await detector.initialize({ onError: (message: string) => { cameraError = message; } });
    await detector.setupDetector('tagStandard41h12', 0, {
      quadDecimate: 1.5,
      quadSigma: 0,
      refineEdges: true,
      decodeSharpening: 0.25,
      debug: false
    });
  }

  async function startCamera() {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      cameraError = 'La cámara necesita HTTPS válido. Abre este scanner desde la URL HTTPS del PC.';
      return;
    }

    isCameraStarting = true;
    cameraError = '';
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      });
      videoElement.srcObject = stream;
      await videoElement.play();
      const [track] = stream.getVideoTracks();
      track.addEventListener('ended', () => {
        calibration = null;
        cameraError = 'La cámara se desconectó. Reiníciala y vuelve a calibrar.';
      });
      cameraStatus = 'Buscando los cuatro marcadores impresos…';
      startDetectionLoop();
    } catch (error) {
      cameraError = error instanceof Error && error.name === 'NotAllowedError'
        ? 'Permite el acceso a la cámara en el navegador y vuelve a intentarlo.'
        : error instanceof Error && error.name === 'NotFoundError'
          ? 'No se encontró una cámara disponible en este teléfono.'
          : error instanceof Error
            ? error.message
            : 'No se pudo iniciar la cámara.';
    } finally {
      isCameraStarting = false;
    }
  }

  function startDetectionLoop() {
    let lastDetection = 0;
    let busy = false;
    const tick = async (timestamp: number) => {
      animationFrame = requestAnimationFrame(tick);
      if (!videoElement || videoElement.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || busy || timestamp - lastDetection < 220) return;
      busy = true;
      lastDetection = timestamp;
      try {
        const width = 640;
        const height = Math.max(1, Math.round(width * videoElement.videoHeight / videoElement.videoWidth));
        processCanvas.width = width;
        processCanvas.height = height;
        overlayCanvas.width = width;
        overlayCanvas.height = height;
        const processContext = processCanvas.getContext('2d', { willReadFrequently: true });
        const overlayContext = overlayCanvas.getContext('2d');
        if (!processContext || !overlayContext || !detector) return;
        processContext.drawImage(videoElement, 0, 0, width, height);
        const image = processContext.getImageData(0, 0, width, height);
        const result = await detector.detect(image, width, height);
        const detections = result.detections;
        const points = detectedMarkerCenters(detections);
        markerCount = points.size;
        missingMarkerNames = markerIds.filter((id) => !points.has(id)).map((id) => markerNames[id]);
        calibration = points.size === 4 ? calibrateMarkers(points, width, height) : null;
        cameraStatus = calibration
          ? 'Tapete calibrado. Mantén los cuatro marcadores visibles para escanear.'
          : points.size === 4
            ? 'Se ven los 4 marcadores, pero su geometría no permite calibrar.'
            : `Marcadores detectados: ${markerCount}/4`;
        drawOverlay(overlayContext, width, height, detections, calibration);
        maybeAutoCapture(points, width, height);
      } catch (error) {
        cameraError = error instanceof Error ? error.message : 'Falló la detección de marcadores.';
        calibration = null;
      } finally {
        busy = false;
      }
    };
    animationFrame = requestAnimationFrame(tick);
  }

  function detectedMarkerCenters(detections: AprilDetection[]): Map<number, Point> {
    const points = new Map<number, Point>();
    for (const detection of detections) {
      if (detection.family === 'tagStandard41h12' && markerIds.includes(detection.id) && detection.hamming === 0) {
        points.set(detection.id, detection.center);
      }
    }
    return points;
  }

  function calibrateMarkers(points: Map<number, Point>, width: number, height: number): number[] | null {
    const topLeft = points.get(0)!;
    const topRight = points.get(1)!;
    const bottomLeft = points.get(2)!;
    const bottomRight = points.get(4)!;
    const corners = [topLeft, topRight, bottomRight, bottomLeft];
    const area = Math.abs(polygonArea(corners));
    if (area < width * height * 0.04 || !isConvexQuadrilateral(corners)) return null;

    const source = [{ u: 0, v: 0 }, { u: 1, v: 0 }, { u: 1, v: 1 }, { u: 0, v: 1 }];
    return solveHomography(source, corners);
  }

  function isConvexQuadrilateral(points: Point[]): boolean {
    const turns = points.map((point, index) => {
      const next = points[(index + 1) % points.length];
      const after = points[(index + 2) % points.length];
      return (next.x - point.x) * (after.y - next.y) - (next.y - point.y) * (after.x - next.x);
    });
    return turns.every((turn) => turn > 1e-5) || turns.every((turn) => turn < -1e-5);
  }

  function polygonArea(points: Point[]): number {
    return points.reduce((sum, point, index) => {
      const next = points[(index + 1) % points.length];
      return sum + point.x * next.y - next.x * point.y;
    }, 0) / 2;
  }

  function solveHomography(source: { u: number; v: number }[], target: Point[]): number[] | null {
    const matrix: number[][] = [];
    source.forEach(({ u, v }, index) => {
      const { x, y } = target[index];
      matrix.push([u, v, 1, 0, 0, 0, -u * x, -v * x, x]);
      matrix.push([0, 0, 0, u, v, 1, -u * y, -v * y, y]);
    });

    for (let column = 0; column < 8; column++) {
      let pivot = column;
      for (let row = column + 1; row < 8; row++) {
        if (Math.abs(matrix[row][column]) > Math.abs(matrix[pivot][column])) pivot = row;
      }
      if (Math.abs(matrix[pivot][column]) < 1e-8) return null;
      [matrix[column], matrix[pivot]] = [matrix[pivot], matrix[column]];
      const divisor = matrix[column][column];
      for (let index = column; index < 9; index++) matrix[column][index] /= divisor;
      for (let row = 0; row < 8; row++) {
        if (row === column) continue;
        const factor = matrix[row][column];
        for (let index = column; index < 9; index++) matrix[row][index] -= factor * matrix[column][index];
      }
    }
    return matrix.map((row) => row[8]);
  }

  function projectPoint(h: number[], u: number, v: number): Point | null {
    const denominator = h[6] * u + h[7] * v + 1;
    if (Math.abs(denominator) < 1e-8) return null;
    return { x: (h[0] * u + h[1] * v + h[2]) / denominator, y: (h[3] * u + h[4] * v + h[5]) / denominator };
  }

  function detectCellAtCenter(matrix: number[], width: number, height: number) {
    const unit = [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }, { x: 0, y: 1 }];
    const image = unit.map(({ x, y }) => projectPoint(matrix, x, y));
    if (image.some((point) => point === null)) return null;
    const inverse = solveHomography(image.map((point) => ({ u: point!.x, v: point!.y })), unit);
    if (!inverse) return null;
    const mat = projectPoint(inverse, width / 2, height / 2);
    if (!mat) return null;
    return cellAtMatPoint(mat.x * MAT_WIDTH_CM, mat.y * MAT_HEIGHT_CM);
  }

  function drawOverlay(
    context: CanvasRenderingContext2D,
    width: number,
    height: number,
    detections: AprilDetection[],
    matrix: number[] | null
  ) {
    context.clearRect(0, 0, width, height);
    context.lineWidth = 2;
    context.font = '14px sans-serif';
    for (const detection of detections) {
      if (detection.family !== 'tagStandard41h12') continue;
      context.strokeStyle = markerIds.includes(detection.id) ? '#50df84' : '#ffba55';
      context.beginPath();
      detection.corners.forEach((corner, index) => index === 0 ? context.moveTo(corner.x, corner.y) : context.lineTo(corner.x, corner.y));
      context.closePath();
      context.stroke();
      context.fillStyle = context.strokeStyle;
      context.fillText(`ID ${detection.id}`, detection.center.x + 8, detection.center.y - 8);
    }
    if (!matrix) return;
    context.strokeStyle = '#51e2a2';
    context.fillStyle = 'rgba(81, 226, 162, .12)';
    context.lineWidth = 2;
    for (const [start, end] of [[0, 1], [1, 2], [2, 3], [3, 0]]) {
      const [u1, v1] = [[0, 0], [1, 0], [1, 1], [0, 1]][start];
      const [u2, v2] = [[0, 0], [1, 0], [1, 1], [0, 1]][end];
      const p1 = projectPoint(matrix, u1, v1);
      const p2 = projectPoint(matrix, u2, v2);
      if (!p1 || !p2) continue;
      context.beginPath(); context.moveTo(p1.x, p1.y); context.lineTo(p2.x, p2.y); context.stroke();
    }
    context.lineWidth = 1;
    for (let row = 1; row < MAT_ROWS; row++) {
      const v = row / MAT_ROWS;
      const left = projectPoint(matrix, 0, v); const right = projectPoint(matrix, 1, v);
      if (left && right) { context.beginPath(); context.moveTo(left.x, left.y); context.lineTo(right.x, right.y); context.stroke(); }
    }
    for (let column = 1; column < MAT_COLUMNS; column++) {
      const u = column / MAT_COLUMNS; const top = projectPoint(matrix, u, 0); const bottom = projectPoint(matrix, u, 1);
      if (top && bottom) { context.beginPath(); context.moveTo(top.x, top.y); context.lineTo(bottom.x, bottom.y); context.stroke(); }
    }
    const detected = detectCellAtCenter(matrix, width, height);
    if (detected) {
      const { row, column } = detected;
      const quad = [[column, row], [column + 1, row], [column + 1, row + 1], [column, row + 1]]
        .map(([c, r]) => projectPoint(matrix, c / MAT_COLUMNS, r / MAT_ROWS));
      if (quad.every((point) => point !== null)) {
        context.fillStyle = 'rgba(255, 200, 60, .35)';
        context.beginPath();
        quad.forEach((point, index) => index === 0 ? context.moveTo(point!.x, point!.y) : context.lineTo(point!.x, point!.y));
        context.closePath(); context.fill();
      }
      if (detected.cell) {
        context.fillStyle = '#ffd36b';
        context.fillText(`Slot: ${detected.cell.label}`, 12, 42);
      }
    }
    context.strokeStyle = '#ffd36b';
    context.beginPath();
    context.moveTo(width / 2 - 12, height / 2); context.lineTo(width / 2 + 12, height / 2);
    context.moveTo(width / 2, height / 2 - 12); context.lineTo(width / 2, height / 2 + 12);
    context.stroke();
    context.fillStyle = 'rgba(81, 226, 162, .12)';
    const boardCorners = [projectPoint(matrix, 0, 0), projectPoint(matrix, 1, 0), projectPoint(matrix, 1, 1), projectPoint(matrix, 0, 1)];
    if (boardCorners.every((point) => point !== null)) {
      context.beginPath();
      boardCorners.forEach((point, index) => index === 0 ? context.moveTo(point!.x, point!.y) : context.lineTo(point!.x, point!.y));
      context.closePath(); context.fill();
    }
    context.fillStyle = '#fff';
    context.fillText('TAPETE CALIBRADO', 12, 22);
  }

  function maybeAutoCapture(points: Map<number, Point>, width: number, height: number) {
    if (!autoCapture || !calibration || isCapturing || isRecognizing || capturedImage) {
      if (!calibration) { stableFrames = 0; previousCenters = null; }
      return;
    }
    let maxMove = Number.POSITIVE_INFINITY;
    if (previousCenters && previousCenters.size === points.size) {
      maxMove = 0;
      for (const [id, point] of points) {
        const previous = previousCenters.get(id);
        if (!previous) { maxMove = Number.POSITIVE_INFINITY; break; }
        maxMove = Math.max(maxMove, Math.hypot(point.x - previous.x, point.y - previous.y));
      }
    }
    previousCenters = new Map(points);
    stableFrames = maxMove <= AUTO_MOVE_TOLERANCE_PX ? stableFrames + 1 : 0;
    if (stableFrames < AUTO_STABLE_FRAMES) return;
    if (Date.now() - lastAutoCaptureAt < AUTO_COOLDOWN_MS) return;
    const detected = detectCellAtCenter(calibration, width, height)?.cell ?? null;
    if (!detected) return;
    const cellKey = `${detected.zone}:${detected.position}`;
    if (cellKey === lastAutoCellKey) return;
    if (slotsForZone(detected.zone) > 0 && availablePositionsForZone(detected.zone).length === 0) return;
    lastAutoCellKey = cellKey;
    lastAutoCaptureAt = Date.now();
    stableFrames = 0;
    void captureCard();
  }

  function discardCapture() {
    capturedImage = '';
    captureCanvas = null;
    capturedCalibration = null;
    captureId = '';
    lastAutoCellKey = '';
    lastAutoCaptureAt = Date.now();
  }

  async function captureCard() {
    cameraError = '';
    captureMessage = '';
    if (!calibration || !stream || videoElement.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      cameraError = 'Se perdieron los marcadores o la cámara. Recupera la calibración antes de capturar.';
      return;
    }
    capturedCalibration = [...calibration];
    const procWidth = overlayCanvas?.width || 640;
    const procHeight = overlayCanvas?.height || 480;
    const detection = detectCellAtCenter(calibration, procWidth, procHeight);
    const detectedCell = detection?.cell ?? null;
    try { boardCards = await loadCameraBoardCards(); } catch {}
    if (detectedCell) {
      const free = availablePositionsForZone(detectedCell.zone);
      selectedZone = detectedCell.zone;
      const wanted = detectedCell.position + 1;
      selectedPosition = slotsForZone(detectedCell.zone) === 0 ? 0 : free.includes(wanted) ? wanted : free[0] || 0;
    }
    const canvas = document.createElement('canvas');
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    const context = canvas.getContext('2d');
    if (!context) { cameraError = 'No se pudo capturar la imagen.'; return; }
    context.drawImage(videoElement, 0, 0);
    captureCanvas = canvas;
    capturedImage = canvas.toDataURL('image/jpeg', 0.88);
    captureId = crypto.randomUUID();
    selectedCardId = '';
    suggestions = [];
    ocrText = '';
    isCapturing = true;
    isRecognizing = true;
    try {
      if (!ocrWorker) ocrWorker = await createWorker('eng');
      const ocrSource = detection ? cropCellCanvas(canvas, capturedCalibration, detection.row, detection.column, procWidth, procHeight) ?? canvas : canvas;
      const result = await ocrWorker.recognize(ocrSource);
      ocrText = result.data.text.trim();
      suggestions = rankDeckCandidates(ocrText, session?.deck_cards || []);
      if (suggestions.length) selectedCardId = String(suggestions[0].card.card_id);
      if (autoCapture && suggestions.length && suggestions[0].score <= AUTO_CONFIRM_MAX_SCORE && selectedCardId) {
        await confirmCardAction();
        return;
      }
      captureMessage = suggestions.length ? 'Revisa la sugerencia y confirma o corrige la carta.' : 'No hubo coincidencia clara. Elige la carta manualmente del deck.';
      await tick();
      capturePanelElement?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch {
      captureMessage = 'No se pudo leer el nombre automáticamente. Puedes elegir la carta del deck manualmente.';
    } finally {
      isCapturing = false;
      isRecognizing = false;
    }
  }

  function cropCellCanvas(
    full: HTMLCanvasElement,
    matrix: number[],
    row: number,
    column: number,
    procWidth: number,
    procHeight: number
  ): HTMLCanvasElement | null {
    const scaleX = full.width / procWidth;
    const scaleY = full.height / procHeight;
    const corners = [
      [column / MAT_COLUMNS, row / MAT_ROWS],
      [(column + 1) / MAT_COLUMNS, row / MAT_ROWS],
      [(column + 1) / MAT_COLUMNS, (row + 1) / MAT_ROWS],
      [column / MAT_COLUMNS, (row + 1) / MAT_ROWS]
    ].map(([u, v]) => projectPoint(matrix, u, v));
    if (corners.some((point) => point === null)) return null;
    const xs = corners.map((point) => point!.x * scaleX);
    const ys = corners.map((point) => point!.y * scaleY);
    const marginX = (Math.max(...xs) - Math.min(...xs)) * 0.15;
    const marginY = (Math.max(...ys) - Math.min(...ys)) * 0.15;
    const sourceX = Math.max(0, Math.floor(Math.min(...xs) - marginX));
    const sourceY = Math.max(0, Math.floor(Math.min(...ys) - marginY));
    const sourceWidth = Math.min(full.width - sourceX, Math.ceil(Math.max(...xs) + marginX) - sourceX);
    const sourceHeight = Math.min(full.height - sourceY, Math.ceil(Math.max(...ys) + marginY) - sourceY);
    if (sourceWidth < 40 || sourceHeight < 40) return null;
    const cropped = document.createElement('canvas');
    cropped.width = sourceWidth * 2;
    cropped.height = sourceHeight * 2;
    const croppedContext = cropped.getContext('2d');
    if (!croppedContext) return null;
    croppedContext.drawImage(full, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, cropped.width, cropped.height);
    return cropped;
  }

  function normalizeText(value: string): string {
    return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '');
  }

  function editDistance(left: string, right: string): number {
    const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
    for (let row = 1; row <= left.length; row++) {
      let diagonal = previous[0];
      previous[0] = row;
      for (let column = 1; column <= right.length; column++) {
        const above = previous[column];
        previous[column] = Math.min(previous[column] + 1, previous[column - 1] + 1, diagonal + (left[row - 1] === right[column - 1] ? 0 : 1));
        diagonal = above;
      }
    }
    return previous[right.length];
  }

  function rankDeckCandidates(text: string, cards: CameraDeckCard[]): Suggestion[] {
    const source = normalizeText(text);
    if (source.length < 4) return [];
    return cards.map((card) => {
      const name = normalizeText(card.name);
      const foundAt = source.indexOf(name);
      const distance = editDistance(source.slice(Math.max(0, foundAt), foundAt >= 0 ? foundAt + name.length : source.length), name);
      const score = foundAt >= 0 ? 0 : distance / Math.max(source.length, name.length, 1);
      return { card, score };
    }).filter((item) => item.score <= 0.62).sort((a, b) => a.score - b.score).slice(0, 5);
  }

  function availablePositionsForZone(zoneValue: string): number[] {
    const zone = zones.find((item) => item.value === zoneValue);
    if (!zone || zone.slots === 0 || !session) return [];
    return Array.from({ length: zone.slots }, (_, index) => index + 1).filter((slot) =>
      !boardCards.some((card) =>
        card.zone === zoneValue && card.position === slot - 1 &&
        (zoneValue === 'extra_monster' || card.player_id === session?.player_id)
      )
    );
  }

  function changeTargetZone(event: Event) {
    selectedZone = (event.currentTarget as HTMLSelectElement).value;
    selectedPosition = availablePositionsForZone(selectedZone)[0] || 0;
  }

  async function confirmCardAction() {
    if (!session || !capturedCalibration || !captureCanvas || !captureId || !selectedCardId) {
      cameraError = 'Falta la calibración, la captura o la carta confirmada.';
      return;
    }
    if (selectedZoneDefinition.slots > 0 && !availablePositionsForZone(selectedZone).includes(selectedPosition)) {
      cameraError = 'Elige una posición libre antes de confirmar.';
      return;
    }
    cameraError = '';
    isSubmitting = true;
    const chosen = session.deck_cards.find((card) => String(card.card_id) === selectedCardId);
    if (!chosen) { cameraError = 'La carta seleccionada no pertenece al deck autorizado.'; isSubmitting = false; return; }
    const sourceZone = { main: 'main_deck', extra: 'extra_deck', side: 'side_deck' }[chosen.section];
    try {
      const response = await cameraFetch('/api/camera-session/cards', {
        method: 'POST',
        body: JSON.stringify({
          client_action_id: captureId,
          card_id: chosen.card_id,
          source_zone: sourceZone,
          zone: selectedZone,
          position: selectedZoneDefinition.slots > 0 ? selectedPosition - 1 : null,
          face_down: faceDown,
          preferred_print_id: chosen.preferred_print_id,
          source_device: 'camera'
        })
      });
      const responseData = await response.json();
      if (!response.ok) {
        if (response.status === 409) {
          boardCards = await loadCameraBoardCards();
          selectedPosition = availablePositionsForZone(selectedZone)[0] || 0;
          throw new Error('Esa posición se ocupó. Elige un slot libre y vuelve a confirmar.');
        }
        throw new Error(responseData.detail || 'No se pudo guardar la acción.');
      }
      boardCards = await loadCameraBoardCards();
      selectedPosition = availablePositionsForZone(selectedZone)[0] || 0;
      captureMessage = `${chosen.name} registrada en ${selectedZoneDefinition.label}.`;
      lastAutoCellKey = '';
      capturedImage = '';
      captureCanvas = null;
      capturedCalibration = null;
      captureId = '';
      selectedCardId = '';
      suggestions = [];
      ocrText = '';
      faceDown = false;
    } catch (error) {
      cameraError = error instanceof Error ? `${error.message} La captura se conserva; puedes reintentar sin duplicarla.` : 'Sin conexión. La captura se conserva para reintentar.';
    } finally {
      isSubmitting = false;
    }
  }

  async function unlinkCamera() {
    try { await cameraFetch('/api/camera-session/revoke', { method: 'POST' }); } catch {}
    clearCameraToken();
    stopCamera();
    await goto('/');
  }

  function stopCamera() {
    if (animationFrame) cancelAnimationFrame(animationFrame);
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
    if (videoElement) videoElement.srcObject = null;
    calibration = null;
  }
</script>

<svelte:head><title>Escáner de cámara | Duel Assistant</title></svelte:head>

<svelte:window on:pagehide={stopCamera} />

{#if isLoading}
  <main class="scanner-state"><p>Validando vínculo y preparando la cámara…</p></main>
{:else if pageError}
  <main class="scanner-state">
    <h1>No se pudo vincular el teléfono</h1>
    <p role="alert">{pageError}</p>
    <a href="/">Volver al inicio</a>
  </main>
{:else if session}
  <main class="scanner-page">
    <header class="scanner-header">
      <div><small>DUEL ASSISTANT · CÁMARA</small><h1>Sala {session.duel_code}</h1><p>{session.player_username}</p></div>
      <button type="button" class="unlink-button" on:click={unlinkCamera}>Desvincular</button>
    </header>

    <section class="scanner-workspace">
      <div class="camera-column">
        <div class="camera-frame" style={`aspect-ratio: ${videoElement?.videoWidth || 4}/${videoElement?.videoHeight || 3}`}>
          <video bind:this={videoElement} autoplay muted playsinline aria-label="Vista de cámara del tapete"></video>
          <canvas bind:this={overlayCanvas} aria-hidden="true"></canvas>
          {#if !stream}<div class="camera-placeholder">La vista de cámara aparecerá aquí.</div>{/if}
        </div>
        <canvas bind:this={processCanvas} class="hidden-canvas" aria-hidden="true"></canvas>
        <div class="calibration-status" class:ready={isCalibrated} aria-live="polite">
          <span class="status-dot"></span>{cameraStatus}
        </div>
        {#if missingMarkerNames.length > 0 && stream}
          <p class="marker-hint">Faltan: {missingMarkerNames.join(', ')}. IDs esperados: 0, 1, 2 y 4 (tagStandard41h12).</p>
        {/if}
        {#if cameraError}<p class="scanner-error" role="alert">{cameraError}</p>{/if}
        <div class="camera-controls">
          {#if !stream}
            <button type="button" class="primary" on:click={startCamera} disabled={isCameraStarting}>{isCameraStarting ? 'Abriendo cámara…' : 'Abrir cámara trasera'}</button>
          {:else}
            <button type="button" class="secondary" on:click={stopCamera}>Detener cámara</button>
            <button type="button" class="secondary" on:click={() => (autoCapture = !autoCapture)} aria-pressed={autoCapture} title="Dispara la captura solo cuando el teléfono está quieto sobre una celda">
              Auto: {autoCapture ? 'ON' : 'OFF'}
            </button>
            <button type="button" class="primary" on:click={captureCard} disabled={!isCalibrated || isCapturing || isRecognizing}>
              {isCapturing ? 'Capturando…' : isRecognizing ? 'Leyendo carta…' : 'Capturar carta'}
            </button>
          {/if}
        </div>
      </div>

      <section class="capture-panel" bind:this={capturePanelElement}>
        <header><small>PASO 2 · PROPUESTA</small><h2>Identificar y confirmar</h2></header>
        {#if capturedImage}
          <img class="capture-preview" src={capturedImage} alt="Captura pendiente de confirmar" />
          {#if ocrText}<details><summary>Texto leído</summary><pre>{ocrText}</pre></details>{/if}
          <label for="candidate-card">Carta sugerida · deck autorizado</label>
          <select id="candidate-card" bind:value={selectedCardId}>
            <option value="">Elige la carta detectada</option>
            {#each suggestions as suggestion (`suggestion-${suggestion.card.card_id}`)}
              <option value={String(suggestion.card.card_id)}>{suggestion.card.name} · coincidencia {Math.round((1 - suggestion.score) * 100)}%</option>
            {/each}
            {#each session.deck_cards.filter((card) => !suggestions.some((item) => item.card.card_id === card.card_id)) as card (`manual-${card.card_id}`)}
              <option value={String(card.card_id)}>{card.name} · {card.section}</option>
            {/each}
          </select>
          <label for="target-zone">Zona destino</label>
          <select id="target-zone" value={selectedZone} on:change={changeTargetZone}>
            {#each zones as zone (zone.value)}<option value={zone.value}>{zone.label}</option>{/each}
          </select>
          {#if selectedZoneDefinition.slots > 0}
            <label for="target-position">Posición</label>
            <select id="target-position" bind:value={selectedPosition} required disabled={availablePositions.length === 0}>
              {#if availablePositions.length === 0}<option value={0}>No hay slots libres</option>{/if}
              {#each availablePositions as slot (slot)}<option value={slot}>{slot}</option>{/each}
            </select>
            {#if availablePositions.length === 0}<p class="scanner-error">No quedan posiciones libres en esta zona.</p>{/if}
          {/if}
          <label class="face-down"><input type="checkbox" bind:checked={faceDown} /> Colocar boca abajo</label>
          <p class="confirmation-hint">La captura se hizo con calibración válida. Esta carta aún no se registra.</p>
          <button type="button" class="primary confirm-button" on:click={confirmCardAction} disabled={!capturedCalibration || !selectedCardId || isSubmitting || (selectedZoneDefinition.slots > 0 && availablePositions.length === 0)}>
            {isSubmitting ? 'Guardando…' : 'Confirmar y registrar'}
          </button>
          <button type="button" class="text-button" on:click={discardCapture}>Descartar captura</button>
        {:else}
          <p>{autoCapture ? 'Mantén el teléfono quieto con la cruz sobre la carta y la captura se dispara sola.' : 'Cuando los cuatro marcadores estén visibles, captura la carta.'} La lectura solo propone una coincidencia; no modifica la partida hasta que confirmes.</p>
        {/if}
        {#if captureMessage}<p class="success-message" role="status">{captureMessage}</p>{/if}
      </section>
    </section>
  </main>
{/if}

<style>
  .scanner-page { min-height: 100vh; padding: 22px; background: #101812; color: #eef2e8; font-family: 'Space Grotesk', sans-serif; }
  .scanner-header { max-width: 1280px; margin: 0 auto 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334137; padding-bottom: 14px; }
  .scanner-header small, .capture-panel header small { color: #d9573b; font: 10px 'DM Mono', monospace; }
  .scanner-header h1 { margin: 5px 0 0; font-size: 27px; }
  .scanner-header p { margin: 2px 0 0; color: #9eaa9d; font-size: 13px; }
  .unlink-button, .secondary { border: 1px solid #516052; background: transparent; color: #e4eadf; padding: 9px 12px; cursor: pointer; }
  .scanner-workspace { max-width: 1280px; margin: auto; display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(300px, .75fr); gap: 20px; align-items: start; }
  .camera-column, .capture-panel { min-width: 0; }
  .camera-frame { width: 100%; max-height: 70vh; min-height: 260px; position: relative; overflow: hidden; display: grid; place-items: center; background: #050806; border: 1px solid #39483c; }
  .camera-frame video, .camera-frame canvas { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; }
  .camera-frame canvas { pointer-events: none; }
  .camera-placeholder { color: #879387; font: 12px 'DM Mono', monospace; }
  .hidden-canvas { display: none; }
  .calibration-status { display: flex; align-items: center; gap: 8px; margin-top: 11px; color: #e1b05c; font: 12px 'DM Mono', monospace; }
  .calibration-status.ready { color: #69cf7b; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
  .marker-hint { color: #aab7a8; font-size: 12px; }
  .scanner-error { padding: 10px; background: #331d18; color: #ff9b81; font-size: 13px; }
  .camera-controls { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 12px; }
  .primary { border: 0; background: #d9573b; color: white; padding: 11px 15px; font: 12px 'DM Mono', monospace; cursor: pointer; }
  .primary:disabled { opacity: .45; cursor: not-allowed; }
  .capture-panel { padding: 17px; background: #17211b; border: 1px solid #344337; }
  .capture-panel h2 { margin: 4px 0 14px; font-size: 20px; }
  .capture-panel > p { color: #afbaad; font-size: 13px; line-height: 1.5; }
  .capture-panel label:not(.face-down) { display: block; margin: 12px 0 5px; color: #b5c2b3; font: 10px 'DM Mono', monospace; }
  .capture-panel select { width: 100%; min-height: 38px; border: 1px solid #526052; background: #101812; color: #f4f4ed; padding: 7px; }
  .capture-preview { width: 100%; max-height: 230px; object-fit: contain; background: #080c09; }
  .capture-panel details { margin-top: 8px; color: #a9b6a8; font-size: 11px; }
  .capture-panel pre { max-height: 80px; overflow: auto; white-space: pre-wrap; font-size: 10px; }
  .face-down { display: flex; align-items: center; gap: 8px; margin: 12px 0; color: #e0e8dc; font-size: 13px; }
  .face-down input { accent-color: #d9573b; }
  .confirm-button { width: 100%; margin-top: 8px; }
  .text-button { width: 100%; margin-top: 7px; border: 0; background: transparent; color: #b5c2b3; padding: 8px; cursor: pointer; }
  .success-message { color: #75d68a !important; }
  .scanner-state { min-height: 100vh; display: grid; place-content: center; justify-items: center; gap: 12px; padding: 24px; background: #101812; color: #eef2e8; text-align: center; font-family: 'DM Mono', monospace; }
  .scanner-state a { color: #e66b4e; }
  @media (max-width: 800px) {
    .scanner-page { padding: 14px; }
    .scanner-workspace { grid-template-columns: 1fr; }
    .camera-frame { min-height: 220px; max-height: 56vh; }
  }
</style>