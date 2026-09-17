<div align="center">

![Oquanta](custom_components/oquanta/brand/icon.png)

</div>

<h1 align="center">Oquanta</h1>

<p align="center"><b>Beta</b> · visual flow editor for Home Assistant</p>

<p align="center">
  <a href="README.sv.md">Svenska</a>
</p>

<p align="center">
  <img alt="Beta" src="https://img.shields.io/badge/build-beta-2563eb">
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-custom%20integration-41BDF5">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-111827">
</p>

Oquanta adds a Homey-style canvas to the Home Assistant sidebar. You draw **When**, **If**, and **Do** cards; Home Assistant runs the result as a normal automation or script. The graph is the editor. Home Assistant is the runtime.

**This is a beta.** Features can still change, and things can break. Try it, but do not rely on it as your only way to run the house yet. The [HACS default store](https://hacs.xyz/docs/publish/include) waits until 1.0. Testers can add this repo as a **custom repository**.

This repository is the **installable integration** (`custom_components/oquanta`). Editor source lives in a separate private repo.

The panel follows Home Assistant’s language (English or Swedish).

---

## Requirements

Home Assistant OS, Supervised, or Container. Administrator. Restart Core after install. The path is always `/config/custom_components/oquanta`.

## Install

### HACS (custom repository)

Oquanta is not in the HACS default store. Add it yourself:

1. Open [Add Oquanta in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=DarkSoulXs&repository=oquanta&category=integration), or in HACS: **⋮ → Custom repositories**, URL `https://github.com/DarkSoulXs/oquanta`, type **Integration**.
2. Enable **pre-release / beta** for this repository (all current tags are beta).
3. Download/install Oquanta, then restart Home Assistant Core.
4. Open **Settings → Devices & services → Add integration → Oquanta**.
5. Open **Oquanta** in the sidebar.

Existing yaml `oquanta:` is imported automatically as a config entry (backward compatible). Do not add a new yaml block for a fresh install.

### Manual zip

1. Download the zip from [Releases](https://github.com/DarkSoulXs/oquanta/releases) (marked beta).
2. Unpack it and copy the folder `custom_components/oquanta` to:

   ```text
   /config/custom_components/oquanta
   ```

3. Open **Settings → Devices & services → Add integration → Oquanta**.
4. Restart Home Assistant Core if the sidebar item is missing.
5. Open **Oquanta** in the sidebar.

Samba or Studio Code: the same folder, next to your other custom components, then restart.

### Updates

If you installed via HACS, update in HACS (keep pre-release enabled). Oquanta also checks GitHub Releases on startup and every twelve hours and can show its own banner. Use **one** update path, not both.

Manual zip: download a newer zip and overwrite the folder.

## Beta — what is there

- Flows that become native Home Assistant automations (`oquanta_<id>`) or scripts (`script.oquanta_*`)
- Live catalog from your instance (entities, areas, services)
- Live test against the house (`automation.trigger` / `script.turn_on`) — **this really turns things on and off**
- Logic, choose, parallel, repeat, stop, and subflows (early)

Save, import, and wires can still misbehave. Please report issues under [Issues](https://github.com/DarkSoulXs/oquanta/issues).

## Uninstall

Remove the Oquanta integration under **Settings → Devices & services**, delete `/config/custom_components/oquanta`, restart Core. If you still have yaml `oquanta:`, remove that too. Automations with id `oquanta_*` and scripts `script.oquanta_*` can be removed in the Home Assistant automations and scripts UI.

## License

MIT. Copyright DarkSoulXs. See [LICENSE](LICENSE).
