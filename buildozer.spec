[app]
# Nombre y paquete de la aplicación
title = VoxPro Wireless
package.name = voxpro
package.domain = com.aj

# Origen del código
source.dir = .
source.include_exts = py,png,jpg,kv,atlas

# Versión de la app
version = 0.1

# Librerías necesarias para la app (sin dependencias pesadas de C++)
requirements = python3,kivy,kivymd,numpy,pyjnius

# Orientación de pantalla
orientation = portrait

# Permisos para micrófono y red (Wi-Fi/UDP)
android.permissions = RECORD_AUDIO, INTERNET, ACCESS_NETWORK_STATE

# Fijar herramientas estables para evitar errores de licencias y Build-Tools 37
android.api = 33
android.minapi = 24
android.ndk = 25b
android.build_tools_version = 34.0.0
android.accept_sdk_license = True
android.archs = arm64-v8a

[buildozer]
# Nivel de registro y permisos de ejecución
log_level = 2
warn_on_root = 1
