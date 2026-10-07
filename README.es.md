# Jeremias / WifiModule para Home Assistant

Integración comunitaria con entidades nativas y un panel **Jeremias** para controlar el recuperador y editar la programación de wifimodule.eu. **No requiere hardware adicional, pero sí Internet y la nube del fabricante.**

La versión **0.5.0b1 es una beta**: control y lectura básica tienen capturas reales; perfiles, modos y programación se han implementado a partir del código público de la web y probado con respuestas simuladas. Falta completar las pruebas autenticadas con equipos reales. No es una integración oficial ni está incluida en el catálogo predeterminado de HACS.

## Qué incluye

- Alta desde la interfaz de Home Assistant, con usuario/contraseña y selección de instalación.
- Apagado, siete velocidades, automático/manual, bypass, boost temporizado y vuelta al horario.
- Selector de perfil activo y duración predeterminada de las órdenes manuales.
- Sensores por recuperador: velocidad real, encendido, boost, bypass, errores, horas del filtro, última comunicación y AQS válidos.
- Perfiles: crear, renombrar, activar y borrar perfiles inactivos.
- Modos: nombre, color, velocidad, automático/manual y bypass; eliminación si no se usan en un horario.
- Editor semanal, copia de días, detección de cambios realizados desde otro cliente y exportación JSON de la programación cargada.
- Historial con gráfico, tabla y fechas opcionales, según los datos que conserve la nube.

Las órdenes afectan a **todos los equipos de la instalación seleccionada**, igual que en la web. El modo «Automático (sondas del equipo)» corresponde al recuperador. La nueva «Regulación por sensores» es independiente y usa las entidades seleccionadas de Home Assistant.

## Regulación automática con Airzone

Desde el panel **Jeremias → Regulación por sensores → Sensores y umbrales**, selecciona las entidades reales, guarda los ajustes y activa **Automático**. También puedes configurar los sensores desde las opciones de la integración y ajustar modo/umbrales mediante las nuevas entidades nativas. La primera instalación queda en **Manual**, sin sensores preseleccionados. No cambian los identificadores ni las llamadas del widget existente.

Se combinan todas las zonas por su mayor demanda normalizada: CO₂ en ppm, TVOC en ppb, humedad opcional en % y CAI opcional. El CAI no sustituye mediciones CO₂/TVOC; úsalo únicamente si conoces la escala y un valor mayor significa peor calidad. La ampliación reutiliza la sesión existente de Airzone Cloud para consultar las lecturas AirQ y publicar CO₂, TVOC y humedad, aunque la integración oficial solo muestre parte de ellas. No solicita otra cuenta ni modifica Airzone.

Incluye velocidades 0–7, límites mínimo/máximo, filtrado, histéresis, confirmación de subida y bajada, intervalo entre órdenes y diagnóstico de variable/zona. **Manual** toma la velocidad reportada y la mantiene sin caducidad, guardándola para restaurarla tras reiniciar. Los controles directos pausan la regulación antes de ejecutar su orden. **Horario Jeremias** devuelve explícitamente el control a la programación.

[Funcionamiento, valores iniciales y fallos](docs/AUTOMATIC_CONTROL.md). La instalación mediante HACS, las lecturas AirQ y la persistencia tras un reinicio real están verificadas en una instalación. Sigue pendiente la prueba de cambios automáticos de velocidad y caducidad de órdenes.

## Instalación manual

1. Necesitas Home Assistant **2026.9.0 o posterior**; las pruebas locales usan 2026.9.3.
2. Descomprime el paquete de instalación en `/config`. Debe quedar `/config/custom_components/wifimodule/manifest.json`.
3. Reinicia Home Assistant. Si actualizas una instalación existente, conserva la entrada de integración y haz antes una copia de su carpeta; no elimines la integración ni vuelvas a introducir las credenciales.
4. Ve a **Ajustes → Dispositivos y servicios → Añadir integración → Jeremias / WifiModule**.
5. Introduce las credenciales de wifimodule.eu en el formulario de HA y elige la instalación. No necesitas YAML ni copiar cookies.
6. Abre **Jeremias** en la barra lateral con un usuario administrador. Los controles y sensores nativos también aparecen en Dispositivos y servicios.

Para HACS: añade `https://github.com/JesusMF23/ha-jeremias-wifimodule` en **HACS → Repositorios personalizados**, categoría **Integración**, descarga la beta y reinicia. Ser instalable desde un repositorio personalizado no significa estar aprobado en el catálogo predeterminado de HACS.

## Primer uso y programación

Al arrancar se espera a que avance la última comunicación del equipo. Si la nube devuelve datos antiguos, los controles seguirán indisponibles. Diez minutos sin avance vuelven a bloquearlos.

Las velocidades manuales **0–7 se mantienen sin caducidad** y se guardan para restaurarlas tras reiniciar, esperando comunicación reciente. **0 es apagado**. Al migrar un Manual antiguo sin velocidad guardada se usa 0. Los temporizadores quedan para Boost y el automático propio del equipo; su caducidad puede devolver el control al horario. Boost dura cinco minutos desde su botón y permite de uno a sesenta en el panel.

Para programar:

1. Crea los **Modos** que utilizarás. Cambiar un modo afecta a todos los horarios que lo usan.
2. Crea o selecciona un **Perfil**.
3. En **Horario semanal**, selecciona cada día, ajusta las horas y los modos y pulsa **Guardar día**. La primera fila empieza a las 00:00, las horas no pueden repetirse y se admiten hasta 150 cambios por semana.
4. **Copiar y guardar** reemplaza el día de destino completo con las filas que tienes en pantalla, incluso si aún no las guardaste en el día original.
5. Activa el perfil. Si hay una orden manual vigente, pulsa **Volver al horario** para que deje de tener prioridad.

La exportación contiene la semana del perfil cargado y las listas de modos/perfiles. No incluye todas las semanas ni permite restaurarlas automáticamente. Guarda una copia antes de reorganizar la programación.

El historial usa la hora local de la instalación. Los temporizadores rechazan vencimientos en una hora duplicada por el cambio de horario de otoño: la API no permite especificar el desfase UTC. Su precisión es de minutos, por lo que una orden puede durar hasta 59 segundos menos.

## Límites y seguridad de funcionamiento

La calibración del instalador, equilibrado de ventiladores, emparejamiento, restablecimiento de fábrica y administración de cuenta permanecen en la web. Requieren documentación y pruebas específicas del modelo. Esta integración no modifica Airzone, sus salidas O1/O2 ni los circuitos de calefacción/refrigeración.

La detección de conflictos del horario comprueba la semana justo antes de guardarla. La API no ofrece una operación atómica de comprobación y escritura: evita editar el mismo perfil a la vez desde dos sitios. Un mensaje de éxito confirma la aceptación de la nube; los sensores solo cambian cuando el equipo comunica su estado real.

Si falla una escritura con resultado incierto, no se reenvía automáticamente. Recarga y revisa el estado antes de repetirla. Si cambia el conjunto de equipos de una instalación, usa **Reconfigurar** en HA para revisar sus miembros antes de volver a controlar.

Las credenciales se guardan en HA y no se envían al panel. Protege las copias de seguridad. Los diagnósticos excluyen credenciales, nombres, identificadores y telemetría. Una exportación de programación sí contiene tus nombres y horarios: revísala antes de compartirla.

[Documentación completa](README.md) · [Protocolo](docs/PROTOCOL.md) · [Pruebas y pendientes](docs/VALIDATION.md)

## Panel renovado y apagado opcional (0.5.0b1)

La misma integración incluye tarjetas por zona, gráficos reales del historial de
Home Assistant (6 h, 24 h y 7 días), deslizadores con valor exacto y casillas para
seleccionar sensores. Los ajustes avanzados quedan separados del uso diario.

El mínimo **0** permite apagar automáticamente cuando la demanda permanece a cero
y todas las lecturas son válidas. La actualización conserva el mínimo guardado
(por defecto 1), el modo Manual y el resto de ajustes. Mover un deslizador manual
no envía órdenes hasta pulsar Aplicar.

Las órdenes ya usan **wifimodule.eu** con las credenciales de la integración; no
se configura la IP local del recuperador. Un cambio de IP por DHCP no cambia esta
ruta. Sigue necesitando Internet: una segunda vía local requiere verificar el
protocolo del equipo y todavía no está implementada.

En cada tarjeta de sensor, **Editar nombre** permite guardar un nombre en Home Assistant. Se usa también en gráficas y diagnóstico, conservando entidades e historial. **Cancelar** descarta el cambio.

## Sensores de distintas marcas, retorno temporal y bypass (0.5.0b1)

Selecciona entidades de cualquier integración de HA en Sensores y umbrales: búsqueda por nombre y filtro por área/habitación. Se admiten CO₂ en ppm, TVOC en ppb o ppm (normalizado a ppb), humedad en % y CAI numérico de escala conocida. Los sensores sin clasificación muestran un aviso para comprobar qué miden. Las unidades incompatibles se explican; no se convierte TVOC en masa a concentración molar. Hasta 32 entidades por variable; gobierna la demanda máxima de la instalación, sin regular salidas individuales. La compatibilidad depende de las entidades expuestas, no de la marca.

En Control manual, elige Sin límite o retorno a Automático/Horario Jeremias y una duración de 1–10080 minutos, también expresable en horas. Aplicar guarda la fecha de vencimiento; reiniciar no alarga el plazo. Para cancelar, selecciona Manual o aplica Sin límite. El retorno a Automático necesita HA funcionando y sensores utilizables; si HA estuvo apagado se procesa al arrancar. El retorno a Horario se envía también a la nube con el vencimiento original (precisión de minutos). Boost mantiene su límite de 60 minutos.

El interruptor Bypass superior y la entidad nativa cambian el bypass sin desactivar Automático. Se conservan la selección y los temporizadores manuales vigentes. La interfaz distingue petición y estado reportado: el equipo puede limitar el bypass. Activarlo no comprueba que el aire exterior esté más fresco; no se añade un algoritmo de refrigeración por temperatura.
