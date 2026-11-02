# Manual de operación de LulaMacaroni

Esta es tu guía para usar el back office (la oficina de atrás) de Lula Macaroni. Está escrita para ti, Lore. Si algo de aquí no coincide con lo que ves en la pantalla, avísale a Jon o pregúntale a Claude en tu proyecto: la guía se corrige, no tú.

> Estado: noviembre de 2026. Algunas partes todavía se están construyendo. Donde una vista aún no existe, lo dice.

## 1. Lo que tienes que saber primero

El sistema junta en un solo lugar las dos líneas de tu negocio:

- **EUA · impresiones (`US-POD`)**: ventas en Shopify (y en Etsy cuando abras la cuenta). Prodigi o Frame It Easy imprimen y envían dentro de Estados Unidos.
- **México · originales (`MX-original`)**: tus obras originales en el catálogo en español. Por ahora, quien quiera comprar te escribe por WhatsApp o correo.

Tres reglas que nunca cambian:

1. **Nada se publica, se gasta, se reembolsa ni se cancela sin tu aprobación.** El sistema prepara, revisa y te avisa. Tú decides.
2. **Tu obra nunca se recorta, se estira ni se regenera con IA.** Si un archivo no sirve para un tamaño, el sistema te lo dice y tú mandas otro archivo o quitas ese tamaño.
3. **Un número que falta no es cero.** Si no llegó el dato, verás “—” o la palabra `faltante`. Un cero solo aparece cuando de verdad es cero.

## 2. Cómo abrir el back office

Hoy el back office corre dentro de tu proyecto de Claude, en el entorno de nube “LulaMacaroni”, que ya tiene guardadas las llaves de Shopify, Prodigi y Google.

- **Para ver las pantallas:** en tu proyecto de Claude escribe, por ejemplo, *“abre el back office y mándame la pantalla de Inicio”*. Claude lo abre y te manda la captura.
- **Para el resumen del día en texto:** escribe *“dame el resumen del día”*. Claude corre el resumen y te lo pega.
- **Para traer datos nuevos:** escribe *“sincroniza Shopify y Prodigi”*. Solo lee de las plataformas y escribe en tu hoja; no cambia nada en la tienda.

Próximamente: una dirección web protegida con contraseña (Cloudflare Access, con tu cuenta del negocio) para abrir todo desde tu teléfono sin pasar por Claude. Nunca se va a publicar sin ese acceso.

### Tu hoja de datos: “LulaMacaroni Operaciones”

Todo lo que ves en el back office sale de una hoja de Google en la cuenta del negocio (lulamacaroni@gmail.com). Puedes abrirla, leerla y escribir en ella.

- Puedes agregar notas en las filas y llenar las pestañas que te tocan (Obras, Variantes de originales de México, Clientes de México, Publicidad, Topes, Contenido).
- **No cambies el nombre de las pestañas ni la primera fila** (los encabezados). El sistema se guía por ellos.
- **No borres filas de Aprobaciones.** Es tu historial.
- Un cambio que haces a mano tarda hasta 30 segundos en aparecer en el back office.
- Si algo se movió por error, pídele a Claude *“repara las pestañas de la hoja”*. Eso nunca borra nada.

## 3. “¿De dónde sale?”

Debajo de cada número hay un botón **¿De dónde sale?**. Al tocarlo ves cuatro cosas:

| Dice | Qué significa |
|---|---|
| **Fuente** | De dónde vino el número (por ejemplo, “Shopify (pedidos)” o “Libro de datos (Clientes)”) |
| **Periodo** | Qué días cuenta (hoy, 7 días, 30 días, o “a la fecha”) |
| **Definición** | Cómo se calcula, en palabras (por ejemplo, “venta bruta − descuentos − reembolsos, sin impuestos ni envío”) |
| **Actualizado** | Cuándo llegó el dato por última vez, y hace cuánto |

Y cada número tiene una de estas calidades:

- **real**: viene directo de la plataforma.
- **~ estimado**: es un cálculo aproximado (por ejemplo, el margen antes de que Prodigi cobre). Lleva una tilde “~” delante.
- **— faltante**: el dato no llegó. No es cero.
- **cero real**: la plataforma dijo que es cero (por ejemplo, “Por recibir: US$0.00” cuando no hay depósitos pendientes).

## 4. Las vistas, una por una

La barra de abajo tiene: Inicio, Alertas, Aprobar, Catálogo, Contenido, Anuncios (Publicidad), Pedidos, Clientes, Investigación y Fuentes.

### Inicio · Resumen del día

Lo primero que ves al abrir. Arriba dice **Hola, Lore** y un recuadro con:

- **Qué pasó**: ventas y pedidos desde ayer.
- **Qué requiere tu atención**: cuántas alertas urgentes y cuántos avisos hay.
- **Tus 3 acciones de hoy**: las tres cosas más importantes, ya en orden. Si no hay nada, dice “Nada urgente. 🎨”.

Abajo vienen los números por canal (Shopify, Etsy, contabilidad) para **Hoy**, **7 días** o **30 días**, comparados con el periodo anterior. Toca el periodo arriba para cambiarlo.

Etsy y la contabilidad (QuickBooks) dicen **fuente no conectada** hasta que existan esas cuentas (ver la sección 6).

### Alertas

La lista completa de avisos, del más urgente al menos urgente. Cada alerta dice qué pasa, de dónde lo sabe, cuándo se actualizó, y trae un enlace a la vista donde se resuelve.

Esta vista **solo lee**. Los arreglos se hacen en la tienda (por ejemplo, en Shopify) o pasan por Aprobar. Ver la sección 7 sobre qué hacer con cada color.

### Aprobar

Aquí decides. Cada tarjeta es algo que el sistema quiere hacer y necesita tu permiso: un listado nuevo, un post, un anuncio, un cambio de presupuesto o de precio, un reembolso, una cancelación, un pedido manual a Prodigi o una respuesta a un cliente fuera de las plantillas.

1. Toca **“Ver exactamente qué se publica”** y revisa el texto, la imagen, el precio o el presupuesto. Lo que ves es exactamente lo que se usará.
2. Toca **Aprobar** o **Rechazar**. Si rechazas, escribe en la nota qué cambiarías.
3. **Si algo cambia después de que aprobaste** (una coma, el precio, el presupuesto), el sistema ya no lo deja pasar y te pide aprobar la versión nueva. Es a propósito: así nadie puede cambiar algo que ya aprobaste.
4. Cada aprobación sirve **una sola vez** y **vence a los 7 días**. Si vence, no pasa nada: se vuelve a preparar cuando haga falta.
5. Todo queda guardado en la pestaña **Aprobaciones** de tu hoja, con fecha y tu nota.

Ver o sincronizar datos nunca necesita aprobación. Solo lo que publica, gasta, reembolsa o cancela.

### Catálogo

Todos tus productos, con filtros arriba: **En venta**, **Con avisos**, **Ocultos o borrador** y **Originales MX**.

Toca un producto para ver su ficha: cada variante (tamaño, papel, marco), su SKU, qué imprenta la imprime, su costo, el margen estimado y la revisión del archivo de impresión:

| Archivo | Qué significa |
|---|---|
| archivo ideal / aceptable | Sirve para ese tamaño |
| resolución baja | No tiene pixeles suficientes para verse bien en ese tamaño |
| no sirve | La proporción no coincide con el tamaño. Nunca se recorta |
| sin revisar | Falta cargar el archivo o sus medidas en la pestaña Variantes |

Avisos que puedes ver en un producto:

- **Ninguna imprenta recibe sus pedidos (ubicación “Manual”)**: si alguien compra, nadie lo imprime. Se arregla en Shopify asignando el producto a Prodigi o a Frame It Easy.
- **Está en dos imprentas**: un pedido podría imprimirse y cobrarse dos veces. Deja cada producto en una sola imprenta.
- **Sin SKU**: no se puede ligar a tu obra, a su archivo ni a los costos.

Los **Originales MX** se cargan a mano en las pestañas Obras y Variantes (línea `MX-original`). Los precios de México se muestran con IVA incluido.

### Contenido

El calendario de 14 días y la fila de piezas para Instagram y Pinterest: ideas, borradores, aprobados, programados, publicados y fallidos. Puedes filtrar por plataforma.

Cada pieza muestra si su aprobación es válida. La aprobación cubre exactamente la plataforma, el formato, el idioma, el texto, la imagen y la fecha. Si cambias cualquiera de esas cosas, la pieza pide aprobación otra vez.

Instagram y Pinterest todavía no están conectados, así que nada se publica solo y los resultados de cada post salen como “—”.

### Anuncios (Publicidad)

Tus campañas planeadas, tus topes de gasto y de dónde llegan las ventas.

- **Campañas**: cada una es una fila en la pestaña Publicidad de tu hoja (plataforma, texto, imagen, destino, público, presupuesto, fechas). Ninguna se lanza sin tu aprobación, y **cada cambio de presupuesto también necesita aprobación**.
- **Topes**: en la pestaña Topes pones cuánto se puede gastar al día, al mes, por plataforma, y qué tan grande puede ser un cambio de presupuesto. Si una campaña pasa un tope, aparece una alerta.
- **De dónde llegan las ventas**: lo que Shopify sabe de cada pedido (etiquetas UTM y el sitio de donde vino la visita). Cuando no es seguro, lo dice.
- **Resultados de Meta, Pinterest o Google**: “fuente no conectada”. Ninguna plataforma de anuncios está conectada todavía, y el sistema nunca manda nada a ellas.

### Pedidos

Tus pedidos en tres grupos: **Necesitan atención**, **En curso** y **Cerrados, cancelados o reembolsados**. Cada pedido dice el canal, qué imprenta lo imprime, el tracking y el margen.

- **Margen** = lo que recibiste + envío cobrado − comisión de Shopify Payments (2.9% + 30¢) − costo de impresión y envío de Prodigi. No incluye impuestos ni anuncios.
- Si falta un costo, dice **“Falta: comisión / coste de impresión / envío de imprenta”** y el margen no se calcula como si fuera cero.
- Los pedidos de prueba no se cuentan.
- Esta vista no muestra datos personales de los compradores.

### Clientes

Quién te compra, de dónde, cuántas veces y qué les debes. Filtros: **Todos**, **EUA**, **México** y **Seguimientos**.

- **EUA**: llegan de Shopify con datos mínimos: un nombre corto, país y estado, cuántos pedidos y cuánto han comprado, si aceptan correos, y cómo llegaron la primera vez. Nunca se guarda su correo, teléfono ni dirección.
- **México**: los escribes tú en la pestaña Clientes de tu hoja (línea `MX-original`).
- **Notas y seguimientos**: escribe la nota y una fecha de seguimiento en la pestaña Clientes. Cuando la fecha pasa, aparece en tu resumen del día.
- Etsy dice “fuente no conectada” hasta que abras la cuenta. Los compradores de Etsy nunca van a una lista de correos de fuera.

### Finanzas (en construcción)

Todavía no es una vista aparte. Mientras tanto:

- En **Inicio** ves la venta del periodo y **Por recibir**: el dinero que Shopify Payments tiene pendiente de depositar a tu banco. La venta y el depósito se muestran por separado: nunca se cuentan dos veces.
- En **Pedidos** ves el margen de cada pedido.
- Gastos, utilidad y conciliación dicen “fuente no conectada” hasta que se conecte QuickBooks.

### Investigación

Lo que dicen eRank y EverBee: keywords con sus búsquedas y competencia, tendencias, precios de la competencia y keywords sugeridas para tus obras. Cada número dice de qué archivo y de qué fecha salió. Si no has subido nada, muestra “—”.

No están conectados por API. Una vez al mes:

1. Exporta un CSV de eRank y otro de EverBee. Ponles un nombre con la herramienta y la fecha, por ejemplo `erank-keywords-2026-11-01.csv`.
2. Arrástralos a la carpeta de Drive **LulaMacaroni Investigación** (cuenta del negocio). No borres los de meses anteriores: con tres meses el sistema ya distingue una keyword que sube de forma sostenida de un pico.
3. Pídele a Claude *“importa la investigación”*. Un archivo que ya se importó no se vuelve a leer.

La guía paso a paso, con las columnas que reconoce, está en [setup/investigacion-es.md](setup/investigacion-es.md).

### Fuentes

Una tabla con cada fuente de datos (Shopify, Prodigi, tu hoja, Etsy, contabilidad, etc.), cómo llega, cuándo se actualizó por última vez y su estado:

| Estado | Qué significa |
|---|---|
| al día | Llegó hace poco |
| atrasada | Hace tiempo que no se actualiza. Pide *“sincroniza …”* |
| con error | La última vez falló. Mira la nota en la misma fila |
| sin conectar | Esa cuenta aún no existe o no está conectada |

## 5. Tu rutina

**Cada día (10 a 20 minutos):**

1. Abre Inicio y lee **Tus 3 acciones de hoy**.
2. Ve a **Aprobar** y decide cada tarjeta.
3. Si hay alertas rojas, atiéndelas primero (sección 7).

**Cada semana:** revisa Catálogo → Con avisos, y Clientes → Seguimientos.

**Cada mes:** exporta los CSV de eRank y EverBee a la carpeta LulaMacaroni Investigación, revisa tus Topes de publicidad y comparte con tu contador lo que te pida.

## 6. “Fuente no conectada”

Quiere decir que esa cuenta todavía no existe o aún no está ligada al sistema. **No es un error y no es cero.** Sus números se muestran como “—”.

Hoy dicen “fuente no conectada”:

- **Etsy**: aún no tienes cuenta de vendedora en Etsy.
- **Contabilidad (QuickBooks)**: falta crear la cuenta.
- **Meta, Pinterest y Google Ads**: no hay ninguna plataforma de anuncios conectada.
- **Instagram y Pinterest (publicaciones)**: no se publican solas todavía.

Cuando se conecte una, su estado en Fuentes cambia a “al día” y sus números empiezan a aparecer.

## 7. Cuando algo está en rojo

Las alertas vienen en tres grupos:

- **Urgente** (en rojo): puede costarte dinero o un pedido. Atiéndela hoy.
- **Requiere atención** (en ámbar): hay que hacerlo pronto.
- **Para saber**: solo información.

Cada alerta trae una línea **Qué hacer:** con el siguiente paso.

| Alerta | Qué haces |
|---|---|
| Productos en venta en “Manual” (ninguna imprenta) | En Shopify, asigna cada producto a Prodigi o a Frame It Easy. Mientras tanto, nadie imprime esos pedidos |
| Productos en dos imprentas | En Shopify, deja cada producto en una sola imprenta |
| Pedido #… con problema | Abre el pedido en Pedidos y lee qué falta. Si hay que reimprimir o cancelar, llega a Aprobar |
| Archivos de impresión que no sirven para su tamaño | Manda un archivo para ese tamaño o quita ese tamaño. Nunca se recorta |
| Aprobación no válida en contenido o campaña | Algo cambió después de que lo aprobaste. Revísalo y apruébalo otra vez si está bien |
| Campaña pasa un tope | Revisa la campaña y el tope. Nada se gasta sin tu aprobación |
| Fuente atrasada o con error | Pide a Claude *“sincroniza …”*. Si sigue con error, avísale a Jon |
| Pedidos de Prodigi que no se ligan a una venta | Revisa en Prodigi de qué pedido se trata. No se adivina |
| Seguimiento vencido | Atiende a ese cliente y cambia la fecha o borra el seguimiento en la pestaña Clientes |
| Aún no hay pedidos reales | Haz un pedido de prueba completo antes del lanzamiento |

Si el back office no abre o dice “No se pudo leer el libro de datos”, casi siempre es la conexión con Google. Pídele a Claude *“revisa la conexión con la hoja”*: la revisión dice qué paso falla, sin mostrar ninguna llave.

## 8. Contraseñas y llaves

Cuando el sistema pase a tus manos, cambias **todas** las contraseñas y creas llaves nuevas, para que nadie más que tú tenga acceso. Hazlo con Jon a tu lado la primera vez.

Reglas:

- Nunca pegues una llave o contraseña en el chat, en un documento ni en el repositorio. Solo van en el entorno de nube de tu proyecto de Claude (Project settings → Cloud environment → el engrane del entorno “LulaMacaroni”).
- Cada llave nueva se pega en una sola línea: `NOMBRE=valor`.
- Los cambios del entorno solo funcionan en **sesiones nuevas** de Claude. Después de cambiar una llave, abre un hilo nuevo.
- Activa la verificación en dos pasos en cada cuenta, con tu teléfono.

### Contraseñas

Cambia la contraseña de cada cuenta del negocio: Google (lulamacaroni@gmail.com y la de Workspace de info@lulamacaroni.com), Shopify, Prodigi, GoDaddy, Canva, eRank, EverBee, Pinterest, Instagram y GitHub. Guárdalas en un administrador de contraseñas.

### Llaves, una por una

| Servicio | Dónde se cambia | Nombre en el entorno |
|---|---|---|
| Shopify | Shopify Dev Dashboard → app “LulaMacaroni Operaciones” → Settings → rotar el client secret | `SHOPIFY_CLIENT_SECRET` |
| Prodigi (real) | Panel de Prodigi → Settings → Integrations → API → generar llave nueva | `PRODIGI_API_KEY` |
| Prodigi (pruebas) | Panel de pruebas de Prodigi → mismo lugar | `PRODIGI_SANDBOX_API_KEY` |
| Google | Google Cloud (lulamacaroni@gmail.com) → proyecto “LulaMacaroni Operaciones” → IAM y administración → Cuentas de servicio → backoffice → Claves → Agregar clave → JSON. Después borra la clave vieja | `GOOGLE_SERVICE_ACCOUNT_JSON_B64` |

Para la llave de Google, el archivo JSON se convierte en una sola línea. En Windows, en PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\ruta\al\archivo.json")) | Set-Clipboard
```

Pega el resultado después de `GOOGLE_SERVICE_ACCOUNT_JSON_B64=` y **borra el archivo descargado**.

Después de cambiar las llaves, abre un hilo nuevo y pídele a Claude *“revisa todas las conexiones”*. Si todo responde, borra las llaves viejas donde todavía existan.

Cuando se conecten Etsy, QuickBooks, Meta o Pinterest, sus llaves se agregan a esta tabla.

## 9. A quién le preguntas

- **Algo de la pantalla o de un número:** pregúntale a Claude en tu proyecto. Toca primero “¿De dónde sale?”.
- **Algo que se rompió o una alerta que no se va:** avísale a Jon.
- **Impuestos, facturas, CFDI o tu LLC:** tu contador.
