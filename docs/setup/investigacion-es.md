# Investigación: cómo subir los exports de eRank y EverBee

Ni eRank ni EverBee están conectados por API. Una vez al mes exportas un archivo CSV de
cada herramienta, lo dejas en una carpeta de Google Drive y el sistema lo lee. La pantalla
**Investigación** del back office muestra keywords, tendencias, precios de la competencia y
keywords sugeridas para tus obras, cada número con el archivo y la fecha de donde salió.

Si no has subido nada, la pantalla muestra “—”. Nunca inventa datos.

## Una sola vez: la carpeta

1. En Google Drive (cuenta lulamacaroni@gmail.com) crea una carpeta llamada exactamente
   **LulaMacaroni Investigación**.
2. Clic derecho en la carpeta → **Compartir**.
3. Pega el correo de la cuenta de servicio (el mismo con el que compartiste la hoja
   “LulaMacaroni Operaciones”; termina en `iam.gserviceaccount.com`).
4. Elige **Lector**, quita la palomita de “Notificar” y da **Enviar**.

## Cada mes (unos 10 minutos)

1. **eRank**: abre la herramienta de keywords, busca los términos que te interesan y usa
   el botón de exportar a CSV. **EverBee**: en la extensión, en la lista de productos o de
   keywords, usa **Export** / exportar a CSV.
2. Ponle al archivo un nombre que diga la herramienta y la fecha, por ejemplo:
   - `erank-keywords-2026-11-01.csv`
   - `everbee-productos-2026-11-01.csv`

   La fecha del nombre es la **fecha del export** que verás en cada número. Si no la
   pones, se usa la fecha del archivo en Drive (y la pantalla lo marca como estimado).
3. Arrastra el archivo a la carpeta **LulaMacaroni Investigación**. No borres los de
   meses anteriores: con tres meses seguidos el sistema ya puede decir si una keyword
   **sube de forma sostenida** o si solo fue un pico.
4. Corre la importación (o pídeselo a Claude):
   `python -m lulamacaroni.connectors.investigacion`
   Cada archivo dice cuántas filas se leyeron. Un archivo que ya se importó no se vuelve a
   leer.

También sirve una **hoja de Google** dentro de la carpeta (se lee su primera pestaña).
Un archivo de **Excel (.xlsx)** no se lee: ábrelo y guárdalo como CSV.

## Qué columnas reconoce

No importa mayúsculas, acentos ni signos. Si una columna no se reconoce, se anota como
“ignorada” en la pestaña **Importaciones** y en la pantalla; nunca se adivina.

| Dato | Nombres de columna que acepta (ejemplos) |
|---|---|
| keyword | Keyword, Search term, Tag, Palabra clave |
| búsquedas al mes | Searches, Avg. Searches, Etsy Searches, Search Volume, Volume, Búsquedas |
| clics | Clicks, Avg. Clicks |
| CTR | CTR, Avg. CTR, Click Rate |
| competencia | Competition, Etsy Competition, Competing listings, Competencia |
| tendencia | Trend, Tendencia |
| mercado | Country, Market, País |
| producto | Title, Product Name, Listing Title, Título |
| tienda | Shop, Shop Name, Tienda |
| precio | Price, Precio |
| moneda | Currency, Moneda (si no viene, se toma del símbolo del precio; si tampoco, USD) |
| ventas al mes | Mo. Sales, Monthly Sales, Est. Monthly Sales |
| ingresos al mes | Mo. Revenue, Monthly Revenue |
| reseñas / favoritos / tags | Reviews, Favorites, Tags |

Un archivo necesita al menos una columna de keyword, o de producto (título o precio). Si
no, queda como **error** en Importaciones con la razón. Si una columna importante sale
como ignorada, cámbiale el nombre en el CSV a uno de la tabla y súbelo otra vez.

Valores como `< 20` o `N/A` se guardan vacíos (“—”), no como cero.

## Cómo leer la pantalla

- **~ / estimado**: búsquedas, competencia, ventas e ingresos son estimaciones de la
  herramienta, no datos de Etsy ni de las tiendas.
- **real**: el precio es el que la herramienta vio publicado el día del export.
- **Tendencia**: “sube 3 meses seguidos” solo aparece con tres exports mensuales; un
  salto de un mes es “pico (aún no es tendencia)”.
- **Oportunidades**: keywords con 100 o más búsquedas al mes, ordenadas por búsquedas por
  cada 100 listings que compiten. Es una lista para revisar, **no una garantía de ventas**;
  tú decides si encaja con Lula.
- **Tipos**: prints, enmarcados, descargables, cojines y wallpaper se separan por las
  palabras de cada keyword o título (por ejemplo “printable” = descargable, “framed” =
  enmarcado).
- **Keywords sugeridas por obra**: keywords importadas que comparten palabras con el
  título, tema, colores o colección de la obra (pestaña Obras). Para probar una, anótala en
  la pestaña **Keywords** con la obra, el canal y el estado (`a-probar`, `probando`,
  `en-uso`, `descartada`), y la fecha `desde`. Al terminar pon `hasta` y el `resultado`:
  así queda el historial.

## Avisos

- Si el último export de una herramienta tiene más de 35 días, Alertas dice “Toca el
  export mensual”.
- Si una keyword sube tres meses seguidos, Alertas lo anota en “Para saber”.

Nada de esta pantalla publica, cambia listings ni gasta: solo lee.
