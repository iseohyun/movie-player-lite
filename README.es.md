# 🎬 Movie Player Lite

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | **Español** | [Português](README.pt-BR.md) | [Deutsch](README.de.md)

Un reproductor de vídeo gratuito para Windows que te permite **recortar solo la parte que necesitas, al instante y sin perder calidad**.

---

## ⬇️ Descarga e instalación

### 👉 [Descargar el instalador de Movie Player Lite (Windows 10 / 11)](https://github.com/iseohyun/movie-player-lite/releases/latest/download/MoviePlayerLite-Setup.exe)

1. **Haz clic en el enlace de arriba.** Se descarga un archivo llamado `MoviePlayerLite-Setup.exe`.
2. **Haz doble clic en el archivo descargado.** Normalmente está en la carpeta `Descargas`.
3. Si aparece una ventana azul **«Windows protegió su PC»**, haz clic en **Más información** → **Ejecutar de todas formas**.
   Windows la muestra con programas hechos por particulares; no significa que el programa tenga algún problema.
4. Elige el idioma y pulsa **Siguiente** hasta el final. Puedes dejar las opciones como están.

   | Opción | Qué hace |
   | :--- | :--- |
   | Carpeta de instalación | Déjala tal cual salvo que necesites otro lugar. |
   | Crear un acceso directo en el escritorio | Márcala si quieres un icono en el escritorio. |
   | Tipos de archivo que se reproducen por defecto | Los tipos marcados (como `.mp4`) se abren con este programa al hacer doble clic. |
   | Descargar la última versión de FFmpeg | **Déjala marcada.** Descarga el componente necesario para cortar y para guardar vídeos de YouTube. Si ya lo tienes, esta opción no aparece. |

5. Pulsa **Instalar**, espera y luego pulsa **Finalizar**. El programa se inicia.

- No hacen falta permisos de administrador. Funciona en Windows 10 / 11 de 64 bits.
- **Para desinstalarlo**, abre `Configuración` → `Aplicaciones` → `Aplicaciones instaladas` en Windows, busca **Movie Player Lite** y pulsa `Desinstalar`.

---

## 🎞️ Qué puedes hacer

- **Corte ultrarrápido sin pérdida de calidad** — no se recodifica nada, así que incluso los vídeos largos tardan segundos.
- **Girar o voltear la imagen y guardarla**, **guardar el fotograma actual como captura**
- **Dibujar sobre el vídeo** — los trazos desaparecen al cabo de un momento; muy útil para explicar algo.
- **Reproducir desde una dirección de YouTube** — la primera vez se transmite al instante y después se reproduce el archivo guardado.
- **Velocidad de reproducción, zoom y desplazamiento, avance fotograma a fotograma, lista de reproducción**
- **Siete idiomas** — 한국어, English, 简体中文, 日本語, Español, Português, Deutsch

---

## 🚀 Primeros pasos

**Abrir un vídeo**
Arrastra un archivo de vídeo a la ventana del programa. O haz clic derecho sobre la imagen y elige `Archivo` → `Abrir`.

**Cortar la parte que quieres**
1. Pulsa `E` para abrir la ventana de edición.
2. Arrastra las **dos líneas verdes** de la línea de tiempo inferior para fijar el inicio y el final.
3. Pulsa **Cortar**. El original no se modifica y se crea un archivo nuevo.

**Ver un vídeo de YouTube**
Pulsa `Ctrl + U` y pega la dirección de YouTube. Úsalo solo con vídeos que tengas derecho a ver.

**Mostrar el menú**
Pulsa `Alt` o haz clic derecho sobre la imagen. Los atajos aparecen a la derecha de cada elemento del menú.

---

## ⌨️ Atajos más usados

| Función | Atajo |
| :--- | :---: |
| Reproducir / Pausar | `Space` |
| Retroceder / avanzar 1 segundo | `←` / `→` |
| Retroceder / avanzar 5 segundos | `Shift + ←` / `Shift + →` |
| Retroceder / avanzar un fotograma | `<` / `>` |
| Subir / bajar volumen | `↑` / `↓` |
| Silenciar | `M` |
| Más rápido / más lento / velocidad normal | `+` / `-` / `0` |
| Pantalla completa / salir | `F` / `Esc` |
| Ventana de edición (corte) | `E` |
| Lista de reproducción | `L` |
| Abrir una dirección de YouTube | `Ctrl + U` |
| Girar (derecha / izquierda) | `]` / `[` |
| Acercar / alejar / restablecer | `Ctrl + +` / `Ctrl + -` / `Ctrl + 0` |
| Guardar vídeo girado · captura | `Ctrl + S` |
| Dibujo sí/no / borrar todo | `D` / `C` |
| Vídeo anterior / siguiente | `PgUp` / `PgDown` |
| Acerca de | `F1` |

Todos los atajos se pueden buscar y cambiar en `Configuración` → `Atajos`.

---

## 🌐 Cambiar el idioma

Elígelo en `Configuración` → `Idioma`. El programa se reinicia y lo aplica al momento. Al principio sigue el idioma de Windows.
No hace falta añadir un paquete de idioma de Windows para mostrar otros idiomas.

---

## ❓ Preguntas frecuentes

**Aparece la ventana «Windows protegió su PC».**
Windows la muestra con programas que no están firmados con un certificado de pago. Haz clic en **Más información** → **Ejecutar de todas formas** para instalar.

**¿Qué es FFmpeg? ¿Lo necesito?**
Es una herramienta gratuita que corta y une vídeo. Sin ella puedes reproducir vídeos, pero no funcionarán el corte ni el guardado de vídeos de YouTube. Deja la opción marcada durante la instalación y se descarga sola.

**No se abre un vídeo de YouTube.**
Puede ocurrir durante un tiempo cuando YouTube cambia su sitio. Descarga el instalador más reciente desde el enlace de arriba e instálalo de nuevo.

**¿Dónde se guardan los vídeos de YouTube?**
En la carpeta `%APPDATA%\MP4-Trim\youtube_cache`. Pega esa ruta en la barra de direcciones del Explorador de archivos para abrirla. Borra archivos de ahí si ocupa demasiado.

**Si desinstalo el programa, ¿se borran mis vídeos?**
No. Solo se elimina el programa; tus archivos de vídeo y los recortes que hayas hecho se quedan donde están.

---

## 🛠️ Para desarrolladores

<details>
<summary>Ejecutar y compilar desde el código fuente</summary>

Necesitas: Python 3.12, `pip install PyQt6 yt-dlp pyinstaller` y FFmpeg en el PATH

```
python movie-player-lite.py      ejecutar desde el código fuente
.\run-dev.bat                    cerrar la app en ejecución -> recompilar -> iniciar
.\build-installer.bat            crear el instalador (requiere Inno Setup 6)
```

- El instalador se genera en `installer_output\MoviePlayerLite-Setup.exe`. Súbelo a una release de GitHub con ese mismo nombre y el enlace de descarga de este documento apuntará a la versión más reciente.
- La versión que muestra el instalador se lee de la primera entrada de `VERSION.md`.
- **Añadir un idioma**: copia `locales/en-US.json` como `locales/<código-de-idioma>.json`, tradúcelo, escribe el nombre visible en `_meta.name` y aparecerá en el menú automáticamente.

```
src/core/       lógica principal (corte y metadatos, atajos, i18n, YouTube)
src/ui/         interfaz (ventana principal, reproductor y línea de tiempo, diálogos)
locales/        archivos de traducción por idioma
installer.iss   script del instalador
```

</details>

---

## 📜 Licencia e historial

- Licencia: [GPL v3](LICENSE). Pulsa `F1` en el programa para ver el software de código abierto que utiliza.
- Historial de cambios: [VERSION.md](VERSION.md)
