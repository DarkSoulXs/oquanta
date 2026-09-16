<p align="center">
  <img src="custom_components/oquanta/www/logo.svg" width="72" alt="Oquanta">
</p>

<h1 align="center">Oquanta</h1>

<p align="center"><b>Alpha</b> · visuell flödeseditor för Home Assistant</p>

<p align="center">
  <a href="README.md">English</a>
</p>

<p align="center">
  <img alt="Alpha" src="https://img.shields.io/badge/build-alpha-d97706">
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-custom%20integration-41BDF5">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-111827">
</p>

Oquanta lägger en Homey-lik duk i Home Assistants sidomeny. Du ritar **När**, **Om** och **Gör**; Home Assistant kör resultatet som en vanlig automation. Grafen är editorn. Automationen är runtime.

**Det här är en alpha.** Funktioner saknas, beteende kan ändras och saker kan gå sönder. Testa gärna, men lita inte på den som enda sätt att styra hemmet ännu. HACS kommer inte förrän 1.0.

Det här repot är **installationen** (`custom_components/oquanta`). Källkoden för editorn ligger i ett separat, privat repo.

Panelen följer Home Assistants språk (svenska eller engelska).

---

## Krav

Home Assistant OS, Supervised eller Container. Administratör. Omstart av Core efter installation. Sökvägen är alltid `/config/custom_components/oquanta`.

## Installation

1. Ladda ner zip från [Releases](https://github.com/DarkSoulXs/oquanta/releases) (märkt alpha).
2. Packa upp och kopiera mappen `custom_components/oquanta` till:

   ```text
   /config/custom_components/oquanta
   ```

3. Lägg till i `configuration.yaml`:

   ```yaml
   oquanta:
   ```

4. Starta om Home Assistant Core.
5. Öppna **Oquanta** i sidomenyn.

Samba eller Studio Code: samma mapp, bredvid dina andra custom components, sedan omstart.

### Uppdateringar

Oquanta kollar GitHub Releases vid start och var tolfte timme. Finns en ny version visas en banner (**Installera** / **Inte nu**). Efter in-app-install: starta om Core när du vill. Samma uppdatering syns under **Inställningar → Uppdateringar**.

Manuellt: ladda ner en nyare zip och skriv över mappen.

## Alpha — vad som finns

- Flöden som blir native Home Assistant-automationer (`oquanta_<id>`)
- Live-katalog från din instans (entiteter, områden, tjänster)
- Live-test mot huset (`automation.trigger`) — **tänder och släcker på riktigt**
- Logik, välj, parallellt, upprepa, stoppa och underflöden (tidigt)

Spara, import och sladdar kan fortfarande bete sig oförutsägbart. Rapportera gärna fel under [Issues](https://github.com/DarkSoulXs/oquanta/issues).

## Avinstallation

Ta bort `oquanta:` ur `configuration.yaml`, radera `/config/custom_components/oquanta`, starta om Core. Automationer med id `oquanta_*` kan tas bort i Home Assistants automationsvy.

## Licens

MIT. Copyright DarkSoulXs. Se [LICENSE](LICENSE).
