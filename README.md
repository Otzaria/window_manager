> **⚠️ Migration Notice**: This plugin is being migrated to [libnativeapi/nativeapi-flutter](https://github.com/libnativeapi/nativeapi-flutter)
>
> The new version is based on a unified C++ core library ([libnativeapi/nativeapi](https://github.com/libnativeapi/nativeapi)), providing more complete and consistent cross-platform native API support.

# window_manager

[![pub version][pub-image]][pub-url] [![Pub Monthly Downloads][pub-dm-image]][pub-dm-url] [![][discord-image]][discord-url] [![All Contributors][all-contributors-image]](#contributors)

[pub-image]: https://img.shields.io/pub/v/window_manager.svg
[pub-url]: https://pub.dev/packages/window_manager
[pub-dm-image]: https://img.shields.io/pub/dm/window_manager.svg
[pub-dm-url]: https://pub.dev/packages/window_manager/score
[discord-image]: https://img.shields.io/discord/884679008049037342.svg
[discord-url]: https://discord.gg/zPa6EZ2jqb
[all-contributors-image]: https://img.shields.io/github/all-contributors/leanflutter/window_manager?color=ee8449&style=flat-square

This plugin provides comprehensive window management capabilities for Flutter desktop applications, enabling full control over window size, position, appearance, close behavior, and listening to events.

---

English | [简体中文](./README-ZH.md)

---

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Platform Support](#platform-support)
- [Documentation](#documentation)
- [Quick Start](#quick-start)
  - [Installation](#installation)
  - [Usage](#usage)
- [Related Articles](#related-articles)
- [Who's using it?](#whos-using-it)
- [Contributors](#contributors)
- [License](#license)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Platform Support

| Linux | macOS | Windows |
| :---: | :---: | :-----: |
|  ✔️   |  ✔️   |   ✔️    |

## Documentation

- [Quick Start](https://leanflutter.dev/documentation/window_manager/quick-start)
- [API Reference](https://pub.dev/documentation/window_manager/latest/window_manager/)
- [Changelog](https://pub.dev/packages/window_manager/changelog)

## Quick Start

### Installation

Add this to your package's `pubspec.yaml` file:

```yaml
dependencies:
  window_manager: ^0.5.1
```

### Usage

```dart
import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Must add this line.
  await windowManager.ensureInitialized();

  WindowOptions windowOptions = WindowOptions(
    size: Size(800, 600),
    center: true,
    backgroundColor: Colors.transparent,
    skipTaskbar: false,
    titleBarStyle: TitleBarStyle.hidden,
  );
  windowManager.waitUntilReadyToShow(windowOptions, () async {
    await windowManager.show();
    await windowManager.focus();
  });

  runApp(MyApp());
}

```

> Please see the example app of this plugin for a full example.

## macOS visibility regression checks

The Otzaria 0.5.2 branch sends `show` and `hide` through
`WindowListener.onWindowEvent` when the corresponding native method actually
changes window visibility. Repeated commands do not add duplicate events. The
visibility operation and its event run together on the main queue; focus,
minimize and restore retain their existing separate callbacks.

On macOS, the following control compiles the complete production
`WindowManager.swift` with the official Flutter framework and runs it against
real `NSWindow` and `NSPanel` instances:

```sh
flutter precache --macos
python3 tool/macos_visibility/run.py \
  --flutter-root /absolute/path/to/flutter \
  --output /absolute/path/to/new-evidence-directory
```

The control records native visibility and the callback thread at delivery. It
checks ordered command bursts, repeated calls, separate windows, unchanged
focus/minimize behavior and a window subclass that deliberately refuses a
visibility change. The same harness must reproduce missing events in the pinned
old source, after the native window has reached the requested state. A build
failure or timeout cannot satisfy that negative control. Raw reports, compiler
output and command exit codes are retained even on failure.

Startup records the activation policy before and after the switch request, its
return value, the launch notification and the state inside the main event loop.
Cases start only with the actual regular policy, a completed launch, the main
event loop and a screen. A failed switch return alone does not describe the
resulting policy. Startup failures produce an owned-process JSON report without
claiming window execution; empty or malformed output keeps its exact command
status and exit code in a separate case result, including in the final summary.
Neither startup errors nor missing reports can satisfy an old-source control.

The existing example integration workflow also runs on PR updates. It uses
Flutter 3.47.7, which supports the Visual Studio 2026 generator, and Ubuntu 24.04
for the legacy example's Ayatana dependency. The Windows and Linux example test
commands are unchanged; no compiler warning is suppressed. The pre-existing
macOS example integration command remains disabled, so that job's setup success
is separate from the required native AppKit gate above.

Portable checks:

```sh
python3 -m unittest discover -s tool/macos_visibility -p test_runner.py
cd packages/window_manager
flutter pub get --no-example
flutter test --no-pub --concurrency=1 test/window_visibility_event_test.dart
```

These use controlled reports or method channels and do not establish native
macOS acceptance. The AppKit control is a functional window test; it is not the
Otzaria application scenario or a resource savings measurement.

## Related Articles

- [Click the dock icon to restore after closing the window](https://leanflutter.dev/blog/click-dock-icon-to-restore-after-closing-the-window/)
- [Making the app single-instanced](https://leanflutter.dev/blog/making-the-app-single-instanced/)

## Who's using it?

- [Airclap](https://airclap.app/) - Send any file to any device. cross platform, ultra fast and easy to use.
- [AuthPass](https://authpass.app/) - Password Manager based on Flutter for all platforms. Keepass 2.x (kdbx 3.x) compatible.
- [Biyi (比译)](https://biyidev.com/) - A convenient translation and dictionary app written in dart / Flutter.
- [BlueBubbles](https://github.com/BlueBubblesApp/bluebubbles-app) - BlueBubbles is an ecosystem of apps bringing iMessage to Android, Windows, and Linux
- [LunaSea](https://github.com/CometTools/LunaSea) - A self-hosted controller for mobile and macOS built using the Flutter framework.
- [Linwood Butterfly](https://github.com/LinwoodCloud/Butterfly) - Open source note taking app written in Flutter
- [RustDesk](https://github.com/rustdesk/rustdesk) - Yet another remote desktop software, written in Rust. Works out of the box, no configuration required.
- [Ubuntu Desktop Installer](https://github.com/canonical/ubuntu-desktop-installer) - This project is a modern implementation of the Ubuntu Desktop installer.
- [UniControlHub](https://github.com/rohitsangwan01/uni_control_hub) - Seamlessly bridge your Desktop and Mobile devices
- [EyesCare](https://bixat.dev/products/EyesCare) - A light-weight application following 20 rule adherence for optimum eye health

## Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/lijy91"><img src="https://avatars.githubusercontent.com/u/3889523?v=4?s=100" width="100px;" alt="LiJianying"/><br /><sub><b>LiJianying</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=lijy91" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/damywise"><img src="https://avatars.githubusercontent.com/u/25608913?v=4?s=100" width="100px;" alt=" A Arif A S"/><br /><sub><b> A Arif A S</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=damywise" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/jpnurmi"><img src="https://avatars.githubusercontent.com/u/140617?v=4?s=100" width="100px;" alt="J-P Nurmi"/><br /><sub><b>J-P Nurmi</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=jpnurmi" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Dixeran"><img src="https://avatars.githubusercontent.com/u/22679810?v=4?s=100" width="100px;" alt="Dixeran"/><br /><sub><b>Dixeran</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=Dixeran" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/nikitatg"><img src="https://avatars.githubusercontent.com/u/96043303?v=4?s=100" width="100px;" alt="nikitatg"/><br /><sub><b>nikitatg</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=nikitatg" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://merritt.codes/"><img src="https://avatars.githubusercontent.com/u/9575627?v=4?s=100" width="100px;" alt="Kristen McWilliam"/><br /><sub><b>Kristen McWilliam</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=Merrit" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Kingtous"><img src="https://avatars.githubusercontent.com/u/39793325?v=4?s=100" width="100px;" alt="Kingtous"/><br /><sub><b>Kingtous</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=Kingtous" title="Code">💻</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/hlwhl"><img src="https://avatars.githubusercontent.com/u/7610615?v=4?s=100" width="100px;" alt="Prome"/><br /><sub><b>Prome</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=hlwhl" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://i.soit.tech/"><img src="https://avatars.githubusercontent.com/u/17426470?v=4?s=100" width="100px;" alt="Bin"/><br /><sub><b>Bin</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=boyan01" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/youxiachai"><img src="https://avatars.githubusercontent.com/u/929502?v=4?s=100" width="100px;" alt="youxiachai"/><br /><sub><b>youxiachai</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=youxiachai" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Allenxuxu"><img src="https://avatars.githubusercontent.com/u/20566897?v=4?s=100" width="100px;" alt="Allen Xu"/><br /><sub><b>Allen Xu</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=Allenxuxu" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://linwood.dev/"><img src="https://avatars.githubusercontent.com/u/20452814?v=4?s=100" width="100px;" alt="CodeDoctor"/><br /><sub><b>CodeDoctor</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=CodeDoctorDE" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/jcbinet"><img src="https://avatars.githubusercontent.com/u/17210882?v=4?s=100" width="100px;" alt="Jean-Christophe Binet"/><br /><sub><b>Jean-Christophe Binet</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=jcbinet" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Jon-Salmon"><img src="https://avatars.githubusercontent.com/u/26483285?v=4?s=100" width="100px;" alt="Jon Salmon"/><br /><sub><b>Jon Salmon</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=Jon-Salmon" title="Code">💻</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/koral--"><img src="https://avatars.githubusercontent.com/u/3340954?v=4?s=100" width="100px;" alt="Karol Wrótniak"/><br /><sub><b>Karol Wrótniak</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=koral--" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/laiiihz"><img src="https://avatars.githubusercontent.com/u/35956195?v=4?s=100" width="100px;" alt="LAIIIHZ"/><br /><sub><b>LAIIIHZ</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=laiiihz" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://www.linkedin.com/in/mikhailkulesh"><img src="https://avatars.githubusercontent.com/u/30557348?v=4?s=100" width="100px;" alt="Mikhail Kulesh"/><br /><sub><b>Mikhail Kulesh</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=mkulesh" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/prateekmedia"><img src="https://avatars.githubusercontent.com/u/41370460?v=4?s=100" width="100px;" alt="Prateek Sunal"/><br /><sub><b>Prateek Sunal</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=prateekmedia" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://ricardoboss.de/"><img src="https://avatars.githubusercontent.com/u/6266356?v=4?s=100" width="100px;" alt="Ricardo Boss"/><br /><sub><b>Ricardo Boss</b></sub></a><br /><a href="https://github.com/leanflutter/window_manager/commits?author=ricardoboss" title="Code">💻</a></td>
    </tr>
  </tbody>
  <tfoot>
    <tr>
      <td align="center" size="13px" colspan="7">
        <img src="https://raw.githubusercontent.com/all-contributors/all-contributors-cli/1b8533af435da9854653492b1327a23a4dbd0a10/assets/logo-small.svg">
          <a href="https://all-contributors.js.org/docs/en/bot/usage">Add your contributions</a>
        </img>
      </td>
    </tr>
  </tfoot>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

## License

[MIT](./LICENSE)
