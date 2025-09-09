# 📚 Alist Cloud Indexer Pro

**Alist Cloud Indexer Pro** es un potente script de Python diseñado para escanear, indexar y organizar archivos alojados en un servidor **Alist**. Transforma tu colección de archivos en una base de datos estructurada y genera una interfaz web interactiva tipo wiki para navegar, buscar y filtrar tus archivos de manera eficiente.

Este script es ideal para ejecutarse en entornos como **Google Colab** o **Jupyter Notebooks**, aprovechando su capacidad para mostrar interfaces HTML enriquecidas directamente en la celda de salida.



---

## ✨ Características Principales

- **Conexión Segura a Alist**: Se conecta a tu instancia de Alist mediante la API, con soporte para autenticación por usuario/contraseña o token.
- **Indexación Recursiva**: Escanea directorios de forma recursiva, extrayendo metadatos clave de cada archivo (nombre, tamaño, fecha de modificación).
- **Etiquetado Automático Inteligente**:
    - Clasifica archivos por **tipo** (imagen, video, documento, etc.).
    - Asigna etiquetas basadas en el **tamaño** (pequeño, mediano, grande).
    - Agrega etiquetas según la **carpeta contenedora**.
    - Incluye etiquetas específicas por **extensión** (ej. `python`, `javascript`, `web`).
- **Organización Virtual**: Crea una estructura de carpetas virtuales que no altera tus archivos originales, permitiéndote navegar por:
    - **Tipo de Archivo** (`/virtual/by_type/image`)
    - **Etiquetas** (`/virtual/by_tag/python`)
    - **Fecha** (`/virtual/by_date/2025-09`)
    - **Tamaño** (`/virtual/by_size/large`)
- **Interfaz Web Interactiva (Wiki)**:
    - Genera un **único archivo HTML** autocontenido.
    - **Búsqueda y filtrado dinámico** por nombre, tipo y etiqueta.
    - **Ordenamiento** por fecha, nombre o tamaño.
    - **Vistas previas** para imágenes y PDFs con carga diferida (*lazy loading*).
    - **Modo claro y oscuro** para comodidad visual.
    - **Diseño responsivo** que se adapta a diferentes tamaños de pantalla.
- **Módulos Opcionales**:
    - **Clasificación con IA**: Un módulo experimental para etiquetar imágenes utilizando modelos de IA como DeepDanbooru (para contenido de anime) o `transformers`.
    - **Reportes Detallados**: Genera un informe en formato Markdown con estadísticas, los archivos más grandes y recomendaciones.
    - **Exportación de Datos**: Guarda el índice completo y la estructura virtual en archivos `JSON` para su uso en otras aplicaciones.

---

## 🚀 Cómo Empezar

Este script está optimizado para ejecutarse en un entorno de notebook. La forma más sencilla de empezar es usando Google Colab.

### Prerrequisitos

- Una instancia de **Alist** en funcionamiento.
- **Python 3.x**.
- Las librerías necesarias (se instalan con `pip`).

### Pasos para la Ejecución

1. **Clonar el Repositorio o Descargar el Script**
   Puedes clonar el repositorio o simplemente descargar el archivo `.py` o `.ipynb`.

2. **Instalar Dependencias**
   Si no estás en un entorno preconfigurado, instala las librerías necesarias:
   ```bash
   pip install requests ipywidgets ipython
   ```
   Para la funcionalidad de clasificación con IA, necesitarás dependencias adicionales que el propio script te indicará cómo instalar.

3. **Ejecutar el Script**
   Abre el script en un Jupyter Notebook o Google Colab y ejecuta la celda principal. El programa te guiará con un menú interactivo:

   - **Opción 1: Configuración Completa**: Te pedirá la URL de tu servidor Alist, tus credenciales y la ruta a escanear.
   - **Opción 2: Inicio Rápido**: Utiliza valores predeterminados para una prueba rápida (ideal para servidores locales).
   - **Opción 3: Cargar Índice Existente**: Carga un archivo `alist_index.json` previamente generado para volver a mostrar la interfaz sin necesidad de escanear de nuevo.

4. **Interactuar con la Interfaz**
   Una vez que el escaneo finalice, la interfaz web se mostrará directamente en la celda de salida del notebook. También se guardará un archivo `alist_wiki.html` en el directorio de trabajo, que puedes abrir en cualquier navegador.

---

## 📂 Archivos Generados

Al finalizar el proceso, el script creará los siguientes archivos:

- **`alist_index.json`**: Un archivo JSON que contiene la base de datos completa de todos los archivos indexados y sus metadatos.
- **`alist_wiki.html`**: El archivo de la interfaz web, listo para ser usado o alojado en cualquier lugar.
- **`report.md` (Opcional)**: Un informe detallado en formato Markdown.
- **`virtual_folders.json` (Opcional)**: Un JSON con la estructura de carpetas virtuales.

---

## 🛠️ Estructura del Código

El código está organizado en clases modulares para facilitar su comprensión y extensión:

- `AlistConfig`: Gestiona la configuración y autenticación con el servidor Alist.
- `AlistClient`: Se encarga de realizar las llamadas a la API de Alist.
- `CloudIndexer`: El núcleo del sistema. Realiza el escaneo de archivos y genera el índice.
- `VirtualOrganizer`: Utiliza el índice para crear la estructura de carpetas virtuales.
- `WikiInterface`: Genera el código HTML, CSS y JavaScript para la interfaz de usuario.
- `ImageClassifier` (Opcional): Contiene la lógica para la clasificación de imágenes con IA.
