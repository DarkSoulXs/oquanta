<p align="center">
  <img src="custom_components/oquanta/www/logo.svg" width="72" alt="Oquanta">
</p>

<h1 align="center">Oquanta</h1>

<p align="center"><b>Beta</b> · visuell flödeseditor för Home Assistant</p>

<p align="center">
  <a href="README.md">English</a>
</p>

<p align="center">
  <img alt="Beta" src="https://img.shields.io/badge/build-beta-2563eb">
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-custom%20integration-41BDF5">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-111827">
</p>

Oquanta lägger en Homey-lik duk i Home Assistants sidomeny. Du ritar **När**, **Om** och **Gör**; Home Assistant kör resultatet som en vanlig automation eller ett skript. Grafen är editorn. Home Assistant är runtime.

**Det här är en beta.** Funktioner kan fortfarande ändras och saker kan gå sönder. Testa gärna, men lita inte på den som enda sätt att styra hemmet ännu. [HACS default-butik](https://hacs.xyz/docs/publish/include) väntar till 1.0. Testers kan lägga till det här repot som **custom repository**.

Det här repot är **installationen** (`custom_components/oquanta`). Källkoden för editorn ligger i ett separat, privat repo.

Panelen följer Home Assistants språk (svenska eller engelska).

---

## Krav

Home Assistant OS, Supervised eller Container. Administratör. Omstart av Core efter installation. Sökvägen är alltid `/config/custom_components/oquanta`.

## Installation

### HACS (custom repository)

Oquanta finns inte i HACS default-butik. Lägg till den själv:

1. Öppna [Lägg till Oquanta i HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=DarkSoulXs&repository=oquanta&category=integration), eller i HACS: **⋮ → Custom repositories**, URL `https://github.com/DarkSoulXs/oquanta`, typ **Integration**.
2. Slå på **pre-release / beta** för det här repot (alla taggar nu är beta).
3. Ladda ner/installera Oquanta, starta sedan om Home Assistant Core.
4. Öppna **Inställningar → Enheter och tjänster → Lägg till integration → Oquanta**.
5. Öppna **Oquanta** i sidomenyn.

Befintlig yaml `oquanta:` importeras automatiskt som config entry (bakåtkompatibilitet). Ny installation behöver inte `configuration.yaml`.

### Manuell zip

1. Ladda ner zip från [Releases](https://github.com/DarkSoulXs/oquanta/releases) (märkt beta).
2. Packa upp och kopiera mappen `custom_components/oquanta` till:

   ```text
   /config/custom_components/oquanta
   ```

3. Öppna **Inställningar → Enheter och tjänster → Lägg till integration → Oquanta**.
4. Starta om Home Assistant Core om sidomenyn saknar Oquanta.
5. Öppna **Oquanta** i sidomenyn.

Samba eller Studio Code: samma mapp, bredvid dina andra custom components, sedan omstart.

### Uppdateringar

Installerade du via HACS: uppdatera i HACS (behåll pre-release på). Oquanta kollar också GitHub Releases vid start och var tolfte timme och kan visa en egen banner. Använd **en** uppdateringsväg, inte båda.

Manuell zip: ladda ner en nyare zip och skriv över mappen.

## Beta — vad som finns

- Flöden som blir native Home Assistant-automationer (`oquanta_<id>`) eller skript (`script.oquanta_*`)
- Live-katalog från din instans (entiteter, områden, tjänster)
- Live-test mot huset (`automation.trigger` / `script.turn_on`) — **tänder och släcker på riktigt**
- Logik, välj, parallellt, upprepa, stoppa och underflöden (tidigt)

Spara, import och sladdar kan fortfarande bete sig oförutsägbart. Rapportera gärna fel under [Issues](https://github.com/DarkSoulXs/oquanta/issues).

## Avinstallation

Ta bort integrationen under **Inställningar → Enheter och tjänster**, radera `/config/custom_components/oquanta`, starta om Core. Har du kvar yaml `oquanta:` tar du bort den också. Automationer med id `oquanta_*` och skript `script.oquanta_*` kan tas bort i Home Assistants automations- och skriptvy.

## Licens

MIT. Copyright DarkSoulXs. Se [LICENSE](LICENSE).
