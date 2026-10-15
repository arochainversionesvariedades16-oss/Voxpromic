[app]
title = VoxPro Wireless
package.name = voxpro
package.domain = com.aj

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 0.1

requirements = python3,kivy,kivymd,numpy,pyjnius

orientation = portrait

android.permissions = RECORD_AUDIO, INTERNET, ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
