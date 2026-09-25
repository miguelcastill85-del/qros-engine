# QROS Mobile — Android M0 (TEST_ONLY)

Aplicación **Flutter para Android**, exclusiva para móviles, sin ejecución de órdenes ni servicios facturables. Los proyectos se mantienen en memoria mientras la aplicación esté abierta. La fixture `DEMO-001` es sintética; no existe backend conectado ni PnL.

## Reproducir

En un entorno con Flutter SDK estable y Android SDK:

```sh
cd product/mobile/flutter_app
flutter create --platforms=android --project-name=qros_mobile_studio --org=app.qros --no-pub .
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

APK resultante: `build/app/outputs/flutter-apk/app-debug.apk`. Los directorios Android generados por Flutter no se versionan en este primer slice; el workflow congela la versión real del SDK en su receipt posterior.

## Flujos M0

- Inicio con métricas explícitamente no económicas.
- Lista de proyectos y fixture ilustrativa `DEMO-001`.
- Creación validada de **borradores locales**, exclusivamente XAUUSD/NQX, BUY/SELL y timeframes permitidos.
- Consulta del proyecto, historial puramente visual y página de seguridad.
- Copiar a portapapeles JSON `TEST_ONLY` sin hashes ni certificaciones inventadas.

## Límites

- No hay persistencia durable en M0: los borradores se pierden cuando se cierra la app.
- No hay conectividad a QROS ni datos reales. No se distribuyen datos de broker ni alfas privados.
- El teléfono no puede mutar estados científicos ni abrir holdout; los permisos externos aún no existen.
- Android debug APK: únicamente pruebas internas; no Play Store ni autorización comercial.
- Backend M2 Linux es una dependencia futura, nunca un cliente de escritorio.

Próximos gates: compilación APK comprobada, pruebas Flutter y Android, recibos autenticados, HEAD externo, backend seguro, pruebas en dispositivo físico y piloto.
