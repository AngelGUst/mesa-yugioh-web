# HTTPS local para probar la cámara

Usa Caddy como proxy inverso y mkcert para crear un certificado de desarrollo confiable para la IP LAN del PC. El frontend, la API y el WebSocket comparten el mismo origen HTTPS.

## Preparación en Windows

Instala mkcert si no está disponible:

```powershell
winget install --id FiloSottile.mkcert --exact
```

Después de instalarlo, abre una terminal nueva. Averigua la IPv4 de la interfaz Wi-Fi o Ethernet conectada a la misma red que el teléfono. En este ejemplo es `192.168.100.80`; reemplázala si cambia.

Desde la raíz del proyecto:

```powershell
New-Item -ItemType Directory -Force .certs
mkcert -install
mkcert -cert-file .certs/duel.pem -key-file .certs/duel-key.pem 192.168.100.80 localhost 127.0.0.1
$caRoot = (mkcert -CAROOT).Trim()
Copy-Item (Join-Path $caRoot 'rootCA.pem') .certs/rootCA.pem
docker compose up -d caddy
docker compose ps
```

Abre `https://192.168.100.80` desde el PC y el teléfono. Para comprobar la API desde PowerShell usa `Invoke-RestMethod https://192.168.100.80/health`.

Para emparejar la cámara, crea el QR desde el tablero del duelo. El teléfono abrirá `https://192.168.100.80/scanner?pairing_token=...`; el scanner canjea el token y elimina el secreto de la barra de direcciones.

## Confiar en el teléfono

Transfiere `.certs/rootCA.pem` al teléfono por un medio privado e instálalo como certificado de CA/confiable en los ajustes del dispositivo. En iOS, después de instalar el perfil, habilita la confianza completa en **Ajustes > General > Información > Ajustes de confianza de certificados**. Los nombres exactos de los menús Android dependen del fabricante.

**Nunca copies ni compartas `rootCA-key.pem`**. Está en el directorio indicado por `mkcert -CAROOT` y permite emitir certificados que el dispositivo confiaría.

## Red y límites

- El teléfono y el PC deben estar en la misma LAN; la IP puede cambiar si el router la asigna por DHCP.
- El firewall de Windows debe permitir conexiones entrantes al puerto `443` (y `80` para la redirección HTTP).
- Los certificados de mkcert son solo para desarrollo local, no para producción.
- Los puertos `5173` y `8000` siguen publicados para desarrollo en el PC. Usa `https://<IP-LAN>` desde el teléfono.
- Caddy pasa `/api/*`, `/health`, `/docs` y el WebSocket al backend. Las demás rutas van al frontend.