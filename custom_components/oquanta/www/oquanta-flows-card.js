class OquantaFlowsCard extends HTMLElement {
  setConfig(config) {
    this._config = config ?? {};
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._asked) {
      this._asked = true;
      void this._load();
    }
  }

  getCardSize() {
    return 3;
  }

  async _load() {
    const hass = this._hass;
    if (!hass) {
      return;
    }
    try {
      const rows = await hass.callWS({ type: "oquanta/list" });
      this._rows = Array.isArray(rows) ? rows : [];
    } catch {
      this._rows = [];
    }
    this._draw();
  }

  async _toggle(row) {
    const hass = this._hass;
    if (!hass) {
      return;
    }
    try {
      await hass.callWS({
        type: "oquanta/set_enabled",
        flow_id: row.id,
        enabled: !row.enabled,
      });
    } catch {
      /* the list refresh shows the state Home Assistant kept */
    }
    this._asked = false;
    await this._load();
  }

  _draw() {
    const hass = this._hass;
    const swedish = String(hass?.language ?? "").startsWith("sv");
    const title = swedish ? "Oquanta-flöden" : "Oquanta flows";
    const empty = swedish ? "Inga flöden än." : "No flows yet.";
    const runLabel = swedish ? "Kör" : "Run";
    const weekLabel = (count) =>
      swedish ? `${count} den här veckan` : `${count} this week`;
    const root = this.shadowRoot ?? this.attachShadow({ mode: "open" });
    const rows = this._rows ?? [];
    root.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 12px 16px; }
        h3 { margin: 0 0 8px; font-size: 1rem; }
        ul { list-style: none; margin: 0; padding: 0; }
        li { display: flex; gap: 8px; align-items: center; padding: 6px 0; }
        button.toggle { border: 0; border-radius: 999px; width: 36px; height: 20px; cursor: pointer; }
        .on { background: #34d399; }
        .off { background: #94a3b8; }
        button.run { border: 0; background: transparent; cursor: pointer; font-size: 0.8rem; }
        .name { font-size: 0.9rem; }
        .note { display: block; font-size: 0.75rem; opacity: 0.7; }
      </style>
      <ha-card>
        <h3>${title}</h3>
        ${rows.length === 0 ? `<p class="note">${empty}</p>` : ""}
        <ul>
          ${rows
            .map(
              (row, index) => {
                const runs = Number(row.runs_week) || 0;
                return `
            <li>
              <button class="toggle ${row.enabled ? "on" : "off"}" data-action="toggle" data-index="${index}" aria-label="${escapeHtml(row.alias || row.id)}"></button>
              <span>
                <span class="name">${escapeHtml(row.alias || row.id)}</span>
                ${runs > 0 ? `<span class="note">${escapeHtml(weekLabel(runs))}</span>` : ""}
                ${row.last_sentence ? `<span class="note">${escapeHtml(row.last_sentence)}</span>` : ""}
              </span>
              ${row.entity_id ? `<button class="run" data-action="run" data-index="${index}">${runLabel}</button>` : ""}
            </li>`;
              },
            )
            .join("")}
        </ul>
      </ha-card>`;
    root.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        const index = Number(button.getAttribute("data-index"));
        const row = rows[index];
        if (!row) {
          return;
        }
        if (button.getAttribute("data-action") === "run") {
          void this._run(row);
          return;
        }
        void this._toggle(row);
      });
    });
  }

  async _run(row) {
    const hass = this._hass;
    if (!hass || !row.entity_id) {
      return;
    }
    const domain = row.kind === "script" ? "script" : "automation";
    const service = row.kind === "script" ? "turn_on" : "trigger";
    try {
      await hass.callService(domain, service, { entity_id: row.entity_id });
    } catch {
      /* Home Assistant keeps the devices as they are */
    }
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

if (!customElements.get("oquanta-flows")) {
  customElements.define("oquanta-flows", OquantaFlowsCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "oquanta-flows",
  name: "Oquanta flows",
  description: "Turn Oquanta flows on or off and read the latest line",
});
