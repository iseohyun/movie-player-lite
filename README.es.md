# 🎬 Movie Player Lite

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | **Español** | [Português](README.pt-BR.md) | [Deutsch](README.de.md)

## 📌 Descripción y propósito
- **Movie Player Lite** es un reproductor y divisor de vídeo sin pérdida ultrarrápido que evita la pérdida de tiempo y de calidad que provoca la recodificación de la línea de tiempo al editar vídeos grandes de alta calidad.
- Su **corte sin pérdida (stream copy) basado en FFmpeg** extrae al instante solo el tramo que necesitas, sin perder calidad.

---

## 🔥 Funciones principales y uso

### 1. Reproductor integrado y deslizador de línea de tiempo
- **Reproductor de vídeo integrado**: basado en QMediaPlayer; reproducir/pausar/pantalla completa con clic, doble clic o la superposición del ratón
- **Línea de tiempo con miniaturas de 10 escenas extraídas de forma asíncrona**: una tira de fotogramas que muestra de un vistazo todo el vídeo
- **Marcadores inteligentes de línea vertical de 1px**: el inicio/fin del corte (líneas verdes de 1px) y la posición actual (línea roja de 1px) se dibujan siempre encima
- **Pausa inteligente**: al sujetar o arrastrar la barra de progreso durante la reproducción se pausa automáticamente para un control preciso

### 2. Barras laterales de opciones, historial y lista de reproducción
- **Panel de opciones izquierdo (`[`)**: silenciar, copiar propiedades de captura, numeración automática y elección de ruta de guardado (misma / output / personalizada)
- **Panel de atajos personalizados (`⌨`)**: cambia y guarda tú mismo los atajos principal y secundario (`hotkeys.json`)
- **Panel de lista de reproducción derecho (`]`)**: gestiona los vídeos recientes, añade archivos o arrástralos, quita elementos con Delete o vacía todo, y limpia automáticamente los archivos que faltan (`playlist_history.json`)
- **Animación de deslizamiento suave**: apertura y cierre optimizados de las barras laterales al pulsar un atajo

---

## ⌨️ Atajos predeterminados

| Función | Principal (Primary) | Secundario (Secondary) |
| :--- | :---: | :---: |
| **Alternar panel de opciones** | `[` | - |
| **Alternar lista de reproducción** | `]` | - |
| **Reproducir / Pausar** | `Space` | `K` |
| **Retroceder / avanzar 1 segundo** | `Left` / `Right` | `J` / `L` |
| **Retroceder / avanzar 5 segundos** | `Shift + Left` / `Shift + Right` | - |
| **Retroceder / avanzar 1 fotograma** | `Ctrl + Left` / `Ctrl + Right` | - |
| **Alternar / salir de pantalla completa** | `F` (o `F11`) | `Esc` |
| **Ver detalles del vídeo** | `?` (Shift + `/`) | - |
| **Quitar elemento de la lista** | `Delete` | - |

---

## 🌐 Idioma
- En **Configuración → Idioma** puedes elegir `Idioma del sistema` (predeterminado) o cualquier idioma instalado. El cambio se aplica **al reiniciar el programa**.
- Idiomas incluidos: 한국어, English, 简体中文, Español, Português (Brasil), Deutsch. Si no hay traducción para el idioma del sistema, se usa el inglés.
- **Añadir un idioma**: copia `locales/en-US.json` como `locales/<código-de-idioma>.json` (por ejemplo `fr-FR.json`), traduce los valores, escribe el nombre visible en `_meta.name` y deja la carpeta `locales` junto al ejecutable. Aparecerá en el menú automáticamente.

---

## 📁 Estructura del proyecto

```
mp4-trim
├ src/
│  ├ core/                  # Lógica principal (corte con FFmpeg, extracción de metadatos/propiedades, atajos personalizados, i18n)
│  ├ ui/                    # Componentes de UI y diálogos
│  │  ├ widgets/            # Línea de tiempo, reproductor de vídeo y campo de tiempo personalizados
│  │  ├ dialogs/            # Diálogo de asignación de atajos
│  │  └ main_window.py      # Diseño de la ventana principal VideoCutterApp y conexión de eventos
│  └ utils/                 # Ventana de registro de excepciones y utilidades de formato de tiempo
├ locales/              : Archivos de traducción por idioma (ko-KR.json, en-US.json, ...)
├ icon.ico              : Icono principal del programa
├ MP4-Trim image.png    : Captura de pantalla del README
├ build.bat             : Script de compilación independiente (versión ligera / paquete completo)
├ mp4-trim.py           : Punto de entrada (Main Entry Point)
├ README.md             : Guía de uso e información del proyecto
└ .gitignore            : Reglas de exclusión de Git
```

---

## 🛠️ Preparar FFmpeg (obligatorio)
1. **Descargar FFmpeg**: [sitio oficial de Gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
2. Descomprime `ffmpeg-release-essentials.zip` y copia `bin/ffmpeg.exe` en la carpeta de este proyecto, o añádelo al **PATH** del sistema.

---

## 📜 Historial de versiones

- **v1.0.5**
  - Marcadores de la línea de tiempo siempre en la parte superior del eje Z (puntos de corte verdes de 1px / línea roja del cabezal de 1px)
  - Pausa automática al manipular la barra de progreso
  - Sistema de atajos personalizados (Primary / Secondary) vinculado a `hotkeys.json`
  - Desplazamiento preciso de 1 fotograma con `Ctrl + ← / →`
  - La tecla `?` muestra las propiedades detalladas del vídeo
  - Corregido un error de liberación de memoria C++ en la animación de la barra lateral
- **v1.0.4**
  - Ventana de registro de excepciones para compilaciones de PyInstaller (`sys.excepthook`)
  - Animación de deslizamiento de las barras laterales (`[` / `]`)
  - Limpieza automática de elementos eliminados o perdidos del historial de la lista
- **v1.0.3**
  - Reproductor de vídeo integrado (QMediaPlayer) y controles superpuestos al pasar el ratón
  - Línea de tiempo de miniaturas (10 escenas extraídas de forma asíncrona con FFmpeg)
  - Lista de reproducción lateral (atajo `]`) con gestión del historial
- **v1.0.2**
  - Enter en el campo del nombre de salida ejecuta el corte; los nombres duplicados se resaltan con un borde
- **v1.0.1**
  - Corregidos errores del historial de tareas y de normalización de rutas
- **v1.0.0**
  - Primera versión (funciones básicas del divisor de vídeo sin pérdida ultrarrápido)
