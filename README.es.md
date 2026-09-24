# Jeremias / WifiModule para Home Assistant

Integración comunitaria con entidades nativas y un panel **Jeremias** para controlar el recuperador y editar la programación de wifimodule.eu. **No requiere hardware adicional, pero sí Internet y la nube del fabricante.**

La versión **0.2.0b1 es una beta**: control y lectura básica tienen capturas reales; perfiles, modos y programación se han implementado a partir del código público de la web y probado con respuestas simuladas. Falta completar las pruebas autenticadas con equipos reales. No es una integración oficial ni está incluida en el catálogo predeterminado de HACS.

## Qué incluye

- Alta desde la interfaz de Home Assistant, con usuario/contraseña y selección de instalación.
- Apagado, siete velocidades, automático/manual, bypass, boost temporizado y vuelta al horario.
- Selector de perfil activo y duración predeterminada de las órdenes manuales.
- Sensores por recuperador: velocidad real, encendido, boost, bypass, errores, horas del filtro, última comunicación y AQS válidos.
- Perfiles: crear, renombrar, activar y borrar perfiles inactivos.
- Modos: nombre, color, velocidad, automático/manual y bypass; eliminación si no se usan en un horario.
- Editor semanal, copia de días, detección de cambios realizados desde otro cliente y exportación JSON de la programación cargada.
- Historial con gráfico, tabla y fechas opcionales, según los datos que conserve la nube.

Las órdenes afectan a **todos los equipos de la instalación seleccionada**, igual que en la web. El modo automático corresponde al recuperador; no conecta por sí solo los sensores AirQ de Airzone.

## Instalación manual

1. Necesitas Home Assistant **2026.9.0 o posterior**; las pruebas locales usan 2026.9.3.
2. Descomprime el paquete de instalación en `/config`. Debe quedar `/config/custom_components/wifimodule/manifest.json`.
3. Reinicia Home Assistant.
4. Ve a **Ajustes → Dispositivos y servicios → Añadir integración → Jeremias / WifiModule**.
5. Introduce las credenciales de wifimodule.eu en el formulario de HA y elige la instalación. No necesitas YAML ni copiar cookies.
6. Abre **Jeremias** en la barra lateral con un usuario administrador. Los controles y sensores nativos también aparecen en Dispositivos y servicios.

Para HACS, cuando el repositorio esté publicado: añade `https://github.com/JesusMF23/ha-jeremias-wifimodule` en **HACS → Repositorios personalizados**, categoría **Integración**, descarga la beta y reinicia. Ser instalable desde un repositorio personalizado no significa estar aprobado en el catálogo predeterminado de HACS.

## Primer uso y programación

Al arrancar se espera a que avance la última comunicación del equipo. Si la nube devuelve datos antiguos, los controles seguirán indisponibles. Diez minutos sin avance vuelven a bloquearlos.

Las órdenes manuales duran **30 minutos** por defecto. La entidad de duración cambia ese valor para órdenes futuras; el panel permite elegir otra duración. **0 significa sin caducidad**, también al apagar. El botón Boost dura cinco minutos; desde el panel admite entre uno y sesenta. Al caducar se vuelve al horario de la nube.

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
