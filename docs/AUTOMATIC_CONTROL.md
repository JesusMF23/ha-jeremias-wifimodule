# Sensor demand control / Regulación por sensores

## Uso en español

En **Jeremias → Regulación por sensores**, abre **Sensores y umbrales**. Selecciona las entidades reales que quieras usar de cada zona y guarda. Activa **Automático** para que Home Assistant gobierne las velocidades. La primera instalación permanece en **Manual** y no selecciona sensores por su nombre. Las opciones nativas de la integración también permiten elegir entidades, incluso si la entrada no ha podido arrancar por falta de conexión con la nube.

El modo HA es independiente del «Automático (sondas del equipo)» del GENIUS. La regulación HA solicita velocidades explícitas usando el controlador WifiModule existente, sin cableado adicional y conservando el bypass actual. Afecta a todas las unidades de la instalación WifiModule seleccionada, igual que el widget original.

### Ajustes iniciales — ejemplos configurables

| Variable | Objetivo | Demanda máxima | Unidad admitida |
|---|---:|---:|---|
| CO₂ | 800 | 1500 | ppm |
| TVOC | 300 | 1000 | ppb |
| Humedad, opcional | 60 | 75 | % |
| CAI, opcional | 50 | 200 | Sin unidad; confirmar escala y sentido |

Estos valores son puntos de partida técnicos, no límites sanitarios ni una garantía de calidad del aire. Los grupos vacíos no intervienen. TVOC en masa no se convierte a ppb sin conocer su equivalencia. CAI no se convierte en CO₂/TVOC. En Airzone Cloud, la biblioteca aioairzone-cloud 0.7.2 representa «good/regular/bad» con 1/151/301. Ese CAI es categórico: permite responder a tres estados, pero no calcular concentraciones ni regular un objetivo CO₂ en ppm. Ver [código de la biblioteca](https://github.com/Noltari/aioairzone-cloud/blob/0.7.2/aioairzone_cloud/const.py). Solo selecciones explícitas participan. Si Airzone Cloud está configurado, la ampliación reutiliza su sesión para consultar el estado real de cada AirQ cada 60 segundos y publicar CO₂, TVOC y humedad como entidades nativas. No usa como lectura actual la captura WebSocket del diagnóstico. Los sensores desconectados, sin medición o con consultas fallidas quedan indisponibles; no se conservan valores anteriores como nuevos. La conexión y autenticación siguen perteneciendo a Airzone Cloud.

Cada lectura se transforma en demanda de 0 a 100% entre objetivo y demanda máxima. Se filtra cada sensor y gana el de mayor demanda, independientemente de su zona o variable. Se interpola entre velocidad mínima y máxima, redondeando hacia arriba. Los valores iniciales son mínimo 1 y máximo 7; no se solicita apagado ni boost desde este regulador.

- Evaluación cada 10 segundos. La latencia real también depende de los sensores, la consulta WifiModule (60 segundos) y la comunicación del equipo.
- Filtro exponencial: constante de subida 30 segundos; bajada 180 segundos. Una demanda residual menor de 0,1% se estabiliza en cero solo cuando la lectura está en el objetivo o por debajo.
- Subida: se confirma durante 30 segundos y puede saltar al nivel requerido. Bajada: se confirma durante 300 segundos y baja un nivel por vez. La histéresis inicial de bajada es 5% de demanda.
- Intervalo mínimo entre órdenes: 60 segundos, también entre renovaciones. Editar los ajustes reinicia filtros y confirmaciones, conservando la separación entre órdenes y cualquier confirmación física pendiente.
- Antigüedad máxima de lecturas: 900 segundos desde `last_reported`. Valores repetidos que HA vuelve a reportar siguen siendo válidos; valores restaurados, no numéricos, fuera de rango o de unidades incompatibles no se usan. Si tu integración deja de reportar lecturas sin cambios, revisa su cadencia antes de aumentar este límite.

### Control manual y diagnóstico

**Pasar a Manual** detiene futuras órdenes y renovaciones de HA, sin mandar otra velocidad ni apagar. La última orden temporal puede seguir vigente hasta su vencimiento. Una orden ya enviada no puede retirarse de la nube; las que siguen pendientes se cancelan antes de transmitirse. Usar los controles existentes de velocidad, modo, bypass, boost, vuelta al horario o perfil activo pausa la regulación antes de ejecutar esa acción manual. El widget y sus entidades conservan identificadores y llamadas.

El panel muestra estado, velocidad física reportada, objetivo, variable/zona dominante, demanda filtrada, tiempo de confirmación y sensores inválidos. También se añaden un selector de regulación, entidades numéricas de configuración y un sensor diagnóstico con estos atributos. Los identificadores se asignan mediante las reglas habituales de HA; usa los selectores de entidades, no nombres supuestos.

Una lectura inválida entre las seleccionadas bloquea bajadas y renovaciones de mantenimiento. Las lecturas válidas restantes pueden justificar una subida. Si todas fallan, no se mandan órdenes. No se interpreta «unavailable» como cero.

### Reinicios y pérdida de comunicación

Modo, selección de sensores y umbrales se guardan en las opciones de la entrada de HA. Al reiniciar no se restaura ninguna demanda ni temporizador antiguo: se esperan lecturas utilizables y avance de comunicación del equipo. Si la nube no permite arrancar la entrada, no se emiten órdenes; las opciones siguen editables.

Las órdenes automáticas son anulaciones manuales temporales de 15 minutos, renovadas aproximadamente cada 5 minutos con todos los sensores seleccionados válidos, incluso al mantener velocidad mientras se confirma una bajada larga. La caducidad utiliza el mecanismo del fabricante ya implementado; cuando vence debe recuperarse su horario. Este comportamiento aún debe comprobarse físicamente en la instalación. Los fallos de HA, de red o de sensores detienen renovaciones; no existe control local independiente de la nube.

Tras una orden aceptada se espera que el equipo reporte la velocidad solicitada. Sin confirmación en 180 segundos se vuelve a Manual con diagnóstico. Un fallo de escritura de resultado incierto desactiva Automático y persiste el fallo para evitar reenvíos ciegos. Hay que revisar el estado y reactivar explícitamente.

Los cambios externos de modo/velocidad en la nube se detectan en las consultas posteriores, con 120 segundos de margen para propagación de una orden propia; entonces se vuelve a Manual. No es detección instantánea ni puede distinguir una orden externa idéntica. Para una intervención manual inequívoca, selecciona Manual en HA o utiliza su widget/control nativo.

## English quick reference

Open **Jeremias → Sensor regulation → Sensors and thresholds**. Select real Home Assistant entities, save and explicitly enable Automatic. First use is Manual with no selected sensors. Native integration options, mode/number entities and the diagnostic sensor expose the same configuration. Existing widget entity IDs and calls remain unchanged.

Selected CO₂ (ppm), TVOC (ppb), optional humidity (%) and optional higher-is-worse AQI are normalized between configurable target/full-demand thresholds. The worst filtered zone/variable wins. Speeds are bounded to configured levels 1–7. Defaults: 30-second rise confirmation, 300-second one-step reduction, asymmetric 30/180-second filtering, 5% downward hysteresis, 60-second command spacing and 900-second reading age limit. These are configurable engineering starting points, not health limits. AQI cannot substitute for measured gases, and missing gas readings are never inferred. An optional shared read-only adapter reuses the configured Airzone Cloud session, polling each AirQ status every 60 seconds and exposing native CO₂/TVOC/humidity entities. Disconnected, missing or failed measurements become unavailable; cached diagnostic WebSocket snapshots are never replayed as current data.

Manual sends no new device command. Existing direct controls pause regulation before their action. Settings/mode persist; restart waits for fresh inputs/device communication. Missing selected readings block reductions and maintenance renewals; all missing readings block commands. A finite 15-minute cloud override is renewed while healthy, allowing the existing vendor schedule to resume after expiration. This fallback still needs physical acceptance. Ambiguous writes or missing physical acknowledgement disable Automatic until explicitly reenabled. External cloud changes are detected after a propagation grace; use HA Manual for immediate, explicit takeover.

## Actual acceptance status

The engine, transport cancellation, persistence, real HA entity/options objects and UI were verified locally with fictional control fixtures. Version 0.3.0b2 was installed through the existing HACS repository. Two real AirQ devices produced changing gas/humidity readings, both gas pairs were selected, and saved thresholds plus Manual mode survived a real HA restart. The original equipment continued reporting fresh telemetry. Automatic actuation, manual takeover during actuation and vendor lease expiry remain physically untested: the equipment had an active manual-off override, which was preserved.
