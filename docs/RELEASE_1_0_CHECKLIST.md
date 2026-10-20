# Aceptación para 1.0.0

20 de octubre de 2026. Versión de preparación: **0.6.2**. Esta lista distingue pruebas automatizadas, observaciones de nube y comprobaciones físicas. Pasar CI no certifica el movimiento del bypass ni el caudal. No se publica 1.0.0 ni se solicita el catálogo predeterminado de HACS hasta cerrar los puntos físicos y revisar los resultados.

## Comprobado por software

- [x] Demanda más desfavorable entre zonas/variables, normalización de unidades, velocidades 0–7, límites, histéresis, subida rápida y bajada lenta.
- [x] Lecturas inválidas, antiguas, restauradas o parcialmente ausentes no autorizan una bajada insegura; recuperación y límites de comandos.
- [x] Manual permanente, ambas vueltas temporizadas, plazo absoluto tras reiniciar, cancelación y toma de control externa.
- [x] Bypass independiente de Automático y del temporizador; Horario usa estado reportado; Manual captura estado actual; confirmación limitada a 180 segundos.
- [x] Transporte HTTP real en localhost: sesión/cookies, renovación acotada, fallos de conexión/respuesta sin reintentos ciegos.
- [x] Perfiles y modos: crear/editar/activar/borrar, editar/copiar días y volver a leerlos por HTTP local; rechazo de ediciones obsoletas, borrado de modo usado y perfil activo. No son pruebas de escritura en la nube del fabricante.
- [x] Migración del registro HA real: conserva el entity_id del ventilador para el widget y las opciones existentes.
- [x] UI EN/ES, controles iniciales, borradores conservados durante bypass, filtro en días, vistas a 390 px sin desbordamiento (preview 0.6.0).
- [x] Empaquetado y versiones coherentes; release normal desde tag después de CI; HACS/hassfest y HA mínimo/actual en CI.

También se ha probado en la vivienda Manual apagado durante cuatro minutos → Horario, con un reinicio en medio: el plazo disminuye tras arrancar y termina en Horario sin intervención. Se ha corregido y observado el bypass en Horario, y se ha editado/restaurado un día de un perfil inactivo en la nube. Son observaciones de interfaz y telemetría, sin medición física independiente.

Las evidencias de instalación, reinicios y telemetría de la vivienda se añaden a [VALIDATION.md](VALIDATION.md). El AirQ del salón no recibe datos porque el webserver Airzone perdió su conexión Wi-Fi, confirmado por el propietario. Esa incidencia externa debe resolverse para probar las dos zonas juntas; no se cambian sus entidades ni se inventan lecturas.

## Incidencia de software pendiente antes de declarar 1.0.0

- [ ] El Historial de la máquina (API de wifimodule.eu) devolvió error en la prueba real, tanto sin fechas como con intervalo explícito. Las gráficas AirQ de Recorder funcionan. Falta comparar con el historial de la web del fabricante en la misma cuenta para distinguir incompatibilidad del cliente, ausencia de soporte/datos o un fallo de la nube. No se afirma que el historial de máquina esté validado; este punto debe cerrarse o documentarse con un tratamiento correcto de la limitación antes de 1.0.0. No se dispone de una sesión de fabricante abierta en Brave para esa comparación.

## Lo que debe comprobar el propietario físicamente

Anota hora, modo, velocidad solicitada/reportada y resultado. No provoques contaminantes ni tapes entradas de aire para crear demanda.

1. **Apagado y velocidades:** en Manual, prueba 0, 1, 4 y 7 brevemente. Comprueba en el mando y por ruido/aire que 0 para los ventiladores y cada nivel cambia realmente. Compara con HA y la web del fabricante. Si discrepan, registra ambas lecturas antes de continuar.
2. **Bypass:** con ventilación en marcha, solicita encendido y apagado en Manual y en Automático por sensores. Verifica la indicación local o el actuador conforme al manual del equipo; la temperatura del aire por sí sola no basta. La petición no debe cambiar el modo ni cancelar un retorno. Las protecciones térmicas del equipo pueden impedir la activación; en ese caso conserva la hora y la indicación local, sin forzarlo. Horario debe mostrar lo reportado y no una petición antigua.
3. **Dos zonas:** recupera el Wi-Fi del webserver del salón. Comprueba que CO₂/TVOC vuelven sin seleccionar entidades nuevas. Con uso normal de la casa, confirma que el diagnóstico identifica la zona/variable de mayor demanda y que la velocidad sube antes de lo que baja. No se debe apagar por perder un sensor.
4. **Mando y widget:** cambia la velocidad con cada uno mientras HA regula. Debe ceder el control; Manual no debe ser sobrescrito por el horario. Después selecciona explícitamente Horario y verifica que vuelve la programación del fabricante.
5. **Fallo de HA/nube:** estando presente y con una prueba corta de Automático, detén HA sin desconectar el equipo. Tras vencer la concesión de 15 minutos desde la última orden aceptada, verifica en el mando que vuelve el horario. Repite un corte breve de Internet si puedes aislar solo la conexión de prueba, y comprueba recuperación sin ráfagas de órdenes. No apagues la alimentación del recuperador para simular este fallo.
6. **Uso continuado:** observa 48 horas con ambas zonas disponibles, incluido un periodo nocturno. Confirma ausencia de oscilaciones, cambios inesperados, errores de comunicación persistentes y avisos falsos de actualización. Revisa también el teléfono y el widget que usas a diario.

Si un paso falla, conservar 0.6.x y corregir/repetirlo. No reiniciar el contador del filtro como prueba.

## Publicación 1.0.0 y HACS (después de aceptación)

- [ ] Cerrar la incidencia de Historial y los resultados anteriores y cualquier diferencia entre mando y nube.
- [ ] Ejecutar CI sobre el commit final; alinear manifest/VERSION/CHANGELOG con 1.0.0 y publicar el tag inmutable mediante Release.
- [ ] Instalar 1.0.0 con HACS, validar/reiniciar HA y verificar versión instalada/ofrecida y conservación de ajustes.
- [ ] Revalidar requisitos oficiales de HACS y abrir la solicitud de inclusión. Este trabajo no la envía.

La acción HACS de 0.6.1 pasa sus diez comprobaciones; avisa de que no se ha declarado la nueva clasificación `categories` del manifest. El campo sigue siendo [opcional](https://contributors.home-assistant.io/core/integrations/categories/). Se probó la nueva categoría, pero la imagen actual de hassfest la rechaza como campo no admitido; se conserva el manifest compatible y se revisará cuando los validadores soporten el mismo esquema. Las actualizaciones de herramientas/Actions de Dependabot permanecen en PR para revisión; no se fusionan automáticamente por pasar CI.

Referencias oficiales revisadas el 20/10/2026: [requisitos generales](https://www.hacs.xyz/docs/publish/start/) y [requisitos de integración](https://www.hacs.xyz/docs/publish/integration/). Licencia, descripción/topics, README, manifest, hacs.json, marca y validadores ya están preparados; la aceptación del catálogo depende de sus mantenedores.
