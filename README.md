# 🐍 Proyecto Python ALIST

> Indexa un servidor Alist por API y genera una wiki HTML navegable con búsqueda, filtros y organización virtual.

## Qué hace

`programa.py` (~1263 líneas) se conecta a una instancia de Alist, escanea directorios de forma recursiva y genera un índice con metadatos (nombre, tamaño, fecha de modificación). A partir del índice crea carpetas virtuales (por tipo, etiqueta, fecha y tamaño) y una interfaz web autocontenida (`alist_wiki.html`), además de exportar el índice a JSON y un reporte opcional en Markdown. Incluye un módulo experimental de clasificación de imágenes con IA (`ImageClassifier`, DeepDanbooru / `transformers`) y está pensado para ejecutarse en Jupyter / Google Colab (usa `IPython.display` e `ipywidgets`).

## Estructura

```text
alist-python-project/
├── programa.py   # Clases AlistConfig, AlistClient, CloudIndexer, ImageClassifier,
│                 # VirtualOrganizer, WikiInterface + main(), quick_start(), etc.
├── .gitignore    # Excluye alist_env/, __pycache__/, *.pyc, .DS_Store
└── README.md     # Este archivo
```

Archivos que genera al ejecutarse (no versionados): `alist_index.json`, `alist_wiki.html`, `report.md`, `virtual_folders.json`.

## Requisitos

- Python 3.x
- Una instancia de Alist accesible (URL + usuario/contraseña o token; también intenta acceso público sin credenciales)
- Dependencias (según el README original del repo):

```bash
pip install requests ipywidgets ipython
```

La clasificación con IA es opcional y pide sus propias dependencias al activarse.

## Cómo correr

```bash
git clone https://github.com/nahataen/alist-python-project.git
cd alist-python-project
pip install requests ipywidgets ipython
python programa.py
```

El menú interactivo ofrece: 1) configuración completa (URL de Alist, credenciales, ruta a escanear), 2) inicio rápido con valores por defecto, 3) cargar un `alist_index.json` existente. Al terminar, abre `alist_wiki.html` en el navegador. En Colab/Jupyter, ejecuta el script por celdas y la interfaz aparece en la salida.

## Notas

- Las credenciales van por teclado al ejecutar el menú; no se guardan en el repo.
- El escaneo usa `POST /api/fs/list` con paginación de 1000 elementos por página; ajusta `per_page` en `AlistClient.list_files` si tu servidor lo requiere.
- Proyecto de uso personal/educativo para organizar tu propio servidor Alist.
