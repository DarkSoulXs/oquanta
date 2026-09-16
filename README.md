<p align="center">
  <img src="custom_components/oquanta/www/logo.svg" width="72" alt="Oquanta">
</p>

<h1 align="center">Oquanta</h1>

<p align="center"><b>Alpha</b> · visual flow editor for Home Assistant</p>

<p align="center">
  <a href="README.sv.md">Svenska</a>
</p>

<p align="center">
  <img alt="Alpha" src="https://img.shields.io/badge/build-alpha-d97706">
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-custom%20integration-41BDF5">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-111827">
</p>

Oquanta adds a Homey-style canvas to the Home Assistant sidebar. You draw **When**, **If**, and **Do** cards; Home Assistant runs the result as a normal automation. The graph is the editor. The automation is the runtime.

**This is an alpha.** Features are missing, behaviour can change, and things can break. Try it, but do not rely on it as your only way to run the house yet. HACS will not ship before 1.0.

This repository is the **installable integration** (`custom_components/oquanta`). Editor source lives in a separate private repo.

The panel follows Home Assistant’s language (English or Swedish).

---

## Requirements

Home Assistant OS, Supervised, or Container. Administrator. Restart Core after install. The path is always `/config/custom_components/oquanta`.

## Install

1. Download the zip from [Releases](https://github.com/DarkSoulXs/oquanta/releases) (marked alpha).
2. Unpack it and copy the folder `custom_components/oquanta` to:

   ```text
   /config/custom_components/oquanta
   ```

3. Open **Settings → Devices & services → Add integration → Oquanta**.
4. Restart Home Assistant Core if the sidebar item is missing.
5. Open **Oquanta** in the sidebar.

Existing yaml `oquanta:` is imported automatically as a config entry (backward compatible). Do not add a new yaml block for a fresh install.

Samba or Studio Code: the same folder, next to your other custom components, then restart.

### Updates

Oquanta checks GitHub Releases on startup and every twelve hours. If a newer version exists, a banner offers **Install** or **Not now**. After an in-app install, restart Core when you are ready. The same update appears under **Settings → Updates**.

Manual: download a newer zip and overwrite the folder.

## Alpha — what is there

- Flows that become native Home Assistant automations (`oquanta_<id>`)
- Live catalog from your instance (entities, areas, services)
- Live test against the house (`automation.trigger`) — **this really turns things on and off**
- Logic, choose, parallel, repeat, stop, and subflows (early)

Save, import, and wires can still misbehave. Please report issues under [Issues](https://github.com/DarkSoulXs/oquanta/issues).

## Uninstall

Remove the Oquanta integration under **Settings → Devices & services**, delete `/config/custom_components/oquanta`, restart Core. If you still have yaml `oquanta:`, remove that too. Automations with id `oquanta_*` can be removed in the Home Assistant automations UI.

## License

MIT. Copyright DarkSoulXs. See [LICENSE](LICENSE).
