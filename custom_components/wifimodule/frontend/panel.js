import { manualControls } from "./manual-controls.js";
import { machineCards } from "./machine-status.js";
import {
  timerInputs,
  bindTimer,
  bypassPresentation,
} from "./control-options.js";
import {
  automaticCard,
  automaticStatus,
  automaticInputs,
  bindAutomatic,
} from "./automatic.js";
import {
  dashboard,
  zoneCards,
  historyChartData,
  historyCharts,
  selectedReadings,
} from "./dashboard.js";
import { bindHistoryInspectors } from "./history-inspector.js";
import {
  addScheduleRow,
  scheduleDraft,
  scheduleEditor,
  scheduleIssue,
  sortedSchedule,
  updateScheduleEditor,
} from "./schedule.js";
import { editDeviceName } from "./sensor-name.js";
import { locales } from "./locales.js";
import { styles } from "./styles.js";
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const color = (v) => (/^#[0-9a-f]{6}$/i.test(v) ? v : "#b4c7dc");
const parseTime = (s) =>
  /^\d{2}:\d{2}$/.test(s)
    ? Number(s.slice(0, 2)) * 60 + Number(s.slice(3))
    : NaN;

class JeremiasPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.page = "controls";
    this.day = 1;
    this.copyDays = [];
    this.entries = [];
    this.busy = false;
    this.dirty = false;
    this.automaticDraft = null;
    this.autoRevision = 0;
    this.view = null;
    this.notice = "";
    this.historyHours = 24;
    this.historyRevision = 0;
    this.openDisclosures = new Set();
  }
  set hass(value) {
    this._hass = value;
    this.t = locales[value.language?.startsWith("es") ? "es" : "en"];
    if (this.isConnected && !this.started) {
      this.started = true;
      this.run(() => this.loadEntries());
    }
  }
  connectedCallback() {
    this.autoTimer = setInterval(async () => {
      if (this.busy || !this.entryId) return;
      const entry = this.entryId;
      const revision = this.autoRevision;
      try {
        const a = await this.api("automatic");
        if (
          entry !== this.entryId ||
          revision !== this.autoRevision ||
          this.busy
        )
          return;
        const selectionChanged =
          JSON.stringify(a.sensors) !== JSON.stringify(this.automatic?.sensors);
        const settingsChanged =
          JSON.stringify(a.settings) !==
          JSON.stringify(this.automatic?.settings);
        this.automatic = a;
        if (a.units && this.view) {
          this.view.units = a.units;
          this.view.ready = a.connection?.device_ready;
          const cards = this.shadowRoot.querySelector("#machine-cards");
          if (cards) cards.innerHTML = machineCards(a.units, this.t);
        }
        const editor = this.shadowRoot.querySelector("#manual-controls");
        if (editor) editor.hidden = a.mode !== "manual";
        const form = this.shadowRoot.querySelector(".manual-form");
        if (form) form.disabled = !a.connection?.device_ready;
        if (selectionChanged) this.loadQualityHistory();
        else if (settingsChanged) this.paintQualityHistory();
        const box = this.shadowRoot.querySelector("#automatic-status");
        if (box) box.innerHTML = automaticStatus(a, this.t.regulation);
        const equipment = this.shadowRoot.querySelector(
          "#equipment-control-state",
        );
        if (equipment) equipment.textContent = this.equipmentControlText();
        const bypassState = bypassPresentation(a, this.t.regulation);
        const bp = this.shadowRoot.querySelector("#regulation-bypass");
        if (bp && !this.busy) {
          bp.checked = bypassState.checked;
          bp.disabled = !a.connection?.device_ready;
        }
        const bs = this.shadowRoot.querySelector("#bypass-status");
        if (bs) bs.textContent = bypassState.text;
        const zones = this.shadowRoot.querySelector("#zone-cards");
        if (zones) zones.innerHTML = zoneCards(a, this.t.regulation);
        for (const [action, active] of [
          ["automatic-enable", a.enabled],
          ["automatic-manual", a.mode === "manual"],
          ["automatic-schedule", a.mode === "schedule"],
        ])
          this.shadowRoot
            .querySelector(`[data-action="${action}"]`)
            ?.setAttribute("aria-pressed", String(active));
      } catch {
        if (
          entry !== this.entryId ||
          revision !== this.autoRevision ||
          this.busy
        )
          return;
        const box = this.shadowRoot.querySelector("#automatic-status");
        if (box)
          box.innerHTML = `<p class="notice error" role="status">${esc(this.t.regulation.refreshFailed)}</p>`;
      }
    }, 10000);
    if (this._hass && !this.started) {
      this.started = true;
      this.run(() => this.loadEntries());
    } else if (this.started && this.automatic) {
      this.loadQualityHistory();
    }
  }
  disconnectedCallback() {
    clearInterval(this.autoTimer);
    this.historyRevision += 1;
  }
  async api(operation, data = {}) {
    return this._hass.callWS({
      type: "wifimodule/manage",
      operation,
      entry_id: this.entryId,
      data,
    });
  }
  async run(task) {
    if (this.busy) return;
    this.rememberManualDraft();
    this.autoRevision += 1;
    this.busy = true;
    this.notice = "";
    this.render();
    try {
      await task();
    } catch {
      this.notice = this.t.error;
      this.failed = true;
    } finally {
      this.busy = false;
      this.render();
    }
  }
  async loadEntries() {
    this.entries = await this.api("list");
    this.entryId = this.entries[0]?.entry_id;
    if (this.entryId) await this.loadView();
  }
  async loadView(profile) {
    const previousProfile = this.view?.profile_id;
    this.automatic = await this.api("automatic");
    this.view = await this.api(
      "view",
      profile === undefined ? {} : { profile_id: Number(profile) },
    );
    if (this.view.profile_id !== previousProfile) {
      this.copyDays = [];
      this.openDisclosures.delete("schedule-copy");
    }
    this.history = null;
    this.historyUnavailable = false;
    this.manualDraft = null;
    this.loadQualityHistory();
    this.dirty = false;
    this.resetDraft();
  }
  async loadQualityHistory() {
    const revision = ++this.historyRevision;
    const entry = this.entryId;
    const ids = [
      ...new Set(selectedReadings(this.automatic).map((s) => s.entity_id)),
    ];
    const end = Date.now(),
      start = end - this.historyHours * 3600000;
    this.qualityHistory = { loading: true };
    this.paintQualityHistory();
    try {
      const params = new URLSearchParams({
        filter_entity_id: ids.join(","),
        end_time: new Date(end).toISOString(),
      });
      const rows = ids.length
        ? await this._hass.callApi(
            "GET",
            `history/period/${new Date(start).toISOString()}?${params}`,
          )
        : [];
      if (!Array.isArray(rows)) throw Error("Invalid history");
      const series = {};
      for (const samples of rows) {
        if (Array.isArray(samples) && ids.includes(samples[0]?.entity_id))
          series[samples[0].entity_id] = samples;
      }
      if (
        revision !== this.historyRevision ||
        entry !== this.entryId ||
        !this.isConnected
      )
        return;
      this.qualityHistory = { series, start, end };
    } catch {
      if (
        revision !== this.historyRevision ||
        entry !== this.entryId ||
        !this.isConnected
      )
        return;
      this.qualityHistory = { error: true };
    }
    this.paintQualityHistory();
  }
  paintQualityHistory() {
    const box = this.shadowRoot.querySelector("#quality-history");
    if (box) {
      this.historyCharts = historyChartData(
        this.automatic,
        this.qualityHistory,
      );
      box.innerHTML = historyCharts(
        this.automatic,
        this.qualityHistory,
        this.t.regulation,
        this._hass.language,
        this.historyCharts,
      );
      this.bindQualityHistory();
    }
  }
  bindQualityHistory() {
    if (!this.historyCharts?.length) return;
    bindHistoryInspectors(
      this.shadowRoot,
      this.historyCharts,
      this.t.regulation,
      this._hass.language,
    );
  }
  resetDraft() {
    this.draft = scheduleDraft(this.view, this.day);
  }
  async mutate(operation, data) {
    const manualDraft = operation === "bypass" ? this.manualDraft : null;
    await this.api(operation, data);
    await this.loadView(
      operation === "profile" &&
        data.operation === "delete" &&
        data.item.id === this.view.profile_id
        ? undefined
        : this.view.profile_id,
    );
    if (manualDraft) this.manualDraft = manualDraft;
    this.notice = this.t.saved;
    this.failed = false;
  }
  async saveSchedule(days, rows, copy) {
    const draft = this.draft;
    const dirty = this.dirty;
    const profile = this.view.profile_id;
    const result = await this.api("edit_days", {
      profile_id: profile,
      days,
      rows,
      revision: this.view.revision,
    });
    const saved = result.saved_days;
    const savedNames = new Intl.ListFormat(this._hass.language).format(
      saved.map((day) => this.t.days[day]),
    );
    const confirmed = `${this.t.scheduleConfirmed} ${savedNames}.`;
    let issue = result.error ? this.t[result.error] || this.t.error : "";
    if (saved.length) {
      if (copy)
        this.copyDays = this.copyDays.filter((day) => !saved.includes(day));
      try {
        await this.loadView(profile);
      } catch {
        issue = issue
          ? `${issue} ${this.t.scheduleReloadFailed}`
          : this.t.scheduleReloadFailed;
      }
      if (copy || issue) {
        this.draft = draft;
        this.dirty = dirty;
      }
    }
    if (copy && !issue) this.openDisclosures.delete("schedule-copy");
    this.failed = !!issue;
    this.notice = issue
      ? [saved.length ? confirmed : "", issue].filter(Boolean).join(" ")
      : copy
        ? confirmed
        : this.t.scheduleSaved;
  }
  confirmDiscard() {
    if (!this.dirty && !this.automaticDraft) return true;
    if (!window.confirm(this.t.discard)) return false;
    this.automaticDraft = null;
    return true;
  }
  options(values, selected) {
    return values
      .map(
        ([value, label]) =>
          `<option value="${esc(value)}" ${String(value) === String(selected) ? "selected" : ""}>${esc(label)}</option>`,
      )
      .join("");
  }
  button(action, label, cls = "", disabled = false) {
    return `<button data-action="${action}" class="${cls}" ${this.busy || disabled ? "disabled" : ""}>${esc(label)}</button>`;
  }
  render() {
    if (!this.t) return;
    const t = this.t,
      v = this.view;
    this.historyCharts =
      this.page === "controls" && v
        ? historyChartData(this.automatic, this.qualityHistory)
        : [];
    this.shadowRoot.innerHTML = `<style>${styles}</style><main><header><button data-action="menu" aria-label="${t.menu}">☰</button><div><h1>${t.title}</h1><div class="muted">${t.subtitle}</div></div>${this.button("refresh", t.refresh)}</header>
    ${
      this.entries.length > 1
        ? `<label>${t.building}<select id="installation" ${this.busy ? "disabled" : ""}>${this.options(
            this.entries.map((e) => [e.entry_id, e.name]),
            this.entryId,
          )}</select></label>`
        : `<p class="installation-name">${this.entries.length ? esc(this.entries[0].name) : this.busy ? t.loading : t.empty}</p>`
    }
    ${automaticCard(this.automatic ? { ...this.automatic, ...this.automaticDraft } : null, t.regulation, this.busy, this.manualControls())}
    ${this.notice ? `<div class="notice ${this.failed ? "error" : ""}" role="alert">${esc(this.notice)}</div>` : ""}
    ${
      v
        ? `<nav role="tablist">${["controls", "schedule", "modes", "profiles", "history"].map((p) => `<button role="tab" data-page="${p}" aria-selected="${this.page === p}" ${this.busy ? "disabled" : ""}>${t[p]}</button>`).join("")}</nav>
    ${this.busy ? `<p role="status">${t.loading}</p>` : ""}<div>${this.content()}</div>
    <footer class="muted">${t.cloud}${v.version ? " · " + esc(v.version) : ""} · ${esc(v.timezone)}<p>${t.advanced}</p>${this.button("export", t.export)}</footer>`
        : ""
    }</main>`;
    this.bindQualityHistory();
    this.shadowRoot.querySelectorAll("[data-page]").forEach(
      (el) =>
        (el.onclick = () => {
          if (this.confirmDiscard()) {
            this.page = el.dataset.page;
            this.dirty = false;
            this.resetDraft();
            this.render();
          }
        }),
    );
    this.shadowRoot
      .querySelectorAll("[data-action]")
      .forEach((el) => (el.onclick = () => this.handle(el.dataset.action, el)));
    const zoneBox = this.shadowRoot.querySelector("#zone-cards");
    if (zoneBox)
      zoneBox.onclick = (event) => {
        const button = event.target.closest("[data-rename-device]");
        if (!button || this.busy) return;
        const sensor = selectedReadings(this.automatic).find(
          (s) => s.device_id === button.dataset.renameDevice,
        );
        if (!sensor) return;
        const entry = this.entryId;
        editDeviceName(
          this.shadowRoot,
          this._hass,
          sensor,
          this.t.regulation,
          async () => {
            const automatic = await this.api("automatic");
            if (entry !== this.entryId || !this.isConnected) return;
            this.automatic = automatic;
            zoneBox.innerHTML = zoneCards(automatic, this.t.regulation);
            this.paintQualityHistory();
          },
        );
      };
    bindAutomatic(this.shadowRoot, (draft) => {
      this.automaticDraft = draft;
    });
    this.shadowRoot.querySelectorAll("[data-disclosure]").forEach((el) => {
      el.open = this.openDisclosures.has(el.dataset.disclosure);
      el.ontoggle = () => {
        if (!el.isConnected) return;
        if (el.open) this.openDisclosures.add(el.dataset.disclosure);
        else this.openDisclosures.delete(el.dataset.disclosure);
      };
    });
    this.shadowRoot.querySelectorAll("[data-history-hours]").forEach(
      (el) =>
        (el.onclick = () => {
          this.historyHours = Number(el.dataset.historyHours);
          this.shadowRoot
            .querySelectorAll("[data-history-hours]")
            .forEach((b) =>
              b.setAttribute(
                "aria-pressed",
                String(Number(b.dataset.historyHours) === this.historyHours),
              ),
            );
          this.loadQualityHistory();
        }),
    );
    const historyRefresh = this.shadowRoot.querySelector(
      "[data-history-refresh]",
    );
    if (historyRefresh)
      historyRefresh.onclick = () => this.loadQualityHistory();
    const updateDuration = this.shadowRoot.querySelector("#return-to")
      ? bindTimer(this.shadowRoot)
      : () => {};
    const bypass = this.shadowRoot.querySelector("#regulation-bypass");
    if (bypass)
      bypass.onchange = () =>
        this.run(() => this.mutate("bypass", { enabled: bypass.checked }));
    const search = this.shadowRoot.querySelector("#sensor-search"),
      area = this.shadowRoot.querySelector("#sensor-area");
    const filterSensors = () =>
      this.shadowRoot.querySelectorAll(".sensor-choice").forEach((el) => {
        el.hidden =
          !el.dataset.search.includes(search.value.trim().toLowerCase()) ||
          (!!area.value && el.dataset.area !== area.value);
      });
    if (search) search.oninput = filterSensors;
    if (area) area.onchange = filterSensors;
    const controlMode = this.shadowRoot.querySelector("#control-mode");
    if (controlMode) controlMode.onchange = updateDuration;
    const speed = this.shadowRoot.querySelector("#speed");
    if (speed)
      speed.oninput = () => {
        updateDuration();
        this.shadowRoot.querySelector("#speed-value").textContent =
          Number(speed.value) === 0
            ? t.off
            : Number(speed.value) === 8
              ? t.boost
              : speed.value;
      };
    const installation = this.shadowRoot.querySelector("#installation");
    if (installation)
      installation.onchange = () => {
        if (this.confirmDiscard()) {
          this.entryId = installation.value;
          this.view = null;
          this.automatic = null;
          this.run(() => this.loadView());
        } else this.render();
      };
    const profile = this.shadowRoot.querySelector("#profile");
    if (profile)
      profile.onchange = () => {
        if (this.confirmDiscard()) this.run(() => this.loadView(profile.value));
        else this.render();
      };
    this.bindSchedule();
    this.shadowRoot
      .querySelectorAll("[data-edit]")
      .forEach(
        (el) =>
          (el.onclick = () =>
            this.editor(el.dataset.kind, Number(el.dataset.edit))),
      );
    this.shadowRoot.querySelectorAll("[data-delete]").forEach(
      (el) =>
        (el.onclick = () => {
          if (window.confirm(t.confirmDelete))
            this.run(() =>
              this.mutate(el.dataset.kind, {
                operation: "delete",
                item: { id: Number(el.dataset.delete) },
              }),
            );
        }),
    );
  }
  bindSchedule() {
    const root = this.shadowRoot;
    const preview = root.querySelector("#schedule-preview");
    if (!preview) return;
    const update = () =>
      updateScheduleEditor(
        root,
        this.view,
        this.day,
        this.draft,
        this.busy,
        this.dirty,
        this.t,
        this.copyDays,
      );
    const changeDraft = () => {
      this.dirty = true;
      update();
    };
    preview.onclick = (event) => {
      const button = event.target.closest("[data-schedule-day]");
      if (!button || this.busy) return;
      const day = Number(button.dataset.scheduleDay);
      if (day === this.day || !this.confirmDiscard()) return;
      this.day = day;
      this.copyDays = [];
      this.openDisclosures.delete("schedule-copy");
      this.dirty = false;
      this.resetDraft();
      this.render();
      root.querySelector(`[data-schedule-day="${day}"]`)?.focus();
    };
    const picker = root.querySelector('[data-disclosure="schedule-copy"]');
    picker.onkeydown = (event) => {
      if (event.key !== "Escape" || !picker.open) return;
      event.stopPropagation();
      picker.open = false;
      picker.querySelector("summary").focus();
    };
    const destinations = [...root.querySelectorAll("[data-schedule-copy-day]")];
    for (const input of destinations) {
      input.onchange = () => {
        this.copyDays = destinations
          .filter((day) => day.checked)
          .map((day) => Number(day.dataset.scheduleCopyDay));
        update();
      };
    }
    root.querySelector("[data-schedule-copy-all]").onclick = () => {
      this.copyDays =
        this.copyDays.length === destinations.length
          ? []
          : destinations.map((input) => Number(input.dataset.scheduleCopyDay));
      update();
    };
    root.querySelectorAll("[data-schedule-time]").forEach((input, i) => {
      input.oninput = () => {
        this.draft[i].time = parseTime(input.value);
        changeDraft();
      };
    });
    root.querySelectorAll("[data-schedule-choice]").forEach((select, i) => {
      const bypass = root.querySelector(`[data-schedule-bypass="${i}"]`);
      bypass.onchange = () => {
        this.draft[i].bypass = bypass.checked;
        changeDraft();
      };
      select.onchange = () => {
        const [type, raw] = select.value.split(":");
        const value = Number(raw);
        const time = this.draft[i].time;
        const direct = type === "speed";
        this.draft[i] = direct
          ? { time, speed: value, bypass: bypass.checked }
          : { time, mode: value };
        bypass.disabled = !direct;
        bypass.parentElement.hidden = !direct;
        changeDraft();
      };
    });
  }
  equipmentControlText() {
    const mode =
      this.automatic?.reported_mode ??
      (this.view?.building?.manual_active === false
        ? "schedule"
        : this.view?.building?.manual_mode);
    return (
      {
        manual: this.t.manual,
        schedule: this.t.scheduleMode,
        auto: this.t.auto,
      }[mode] ?? this.t.unknown
    );
  }
  rememberManualDraft() {
    const q = (s) => this.shadowRoot.querySelector(s);
    if (!q("#speed")) return;
    this.manualDraft = {
      speed: Number(q("#speed").value),
      mode: q("#control-mode").value,
      return_to: q("#return-to").value,
      duration: q("#duration").value,
      unit: q("#duration-unit").value,
    };
  }
  manualControls() {
    if (!this.view) return "";
    return (
      manualControls(
        this.automatic,
        this.view,
        this.t,
        this.busy,
        this.manualDraft,
      ) +
      `<p class="muted">${esc(this.t.regulation.equipmentControl)}: <span id="equipment-control-state">${esc(this.equipmentControlText())}</span></p>`
    );
  }
  content() {
    const t = this.t,
      v = this.view;
    if (this.page === "controls")
      return `${dashboard(this.automatic, this.qualityHistory, this.historyHours, t.regulation, this._hass.language, this.historyCharts)}<section aria-label="${esc(t.maintenance)}"><h2>${esc(t.maintenance)}</h2><div id="machine-cards" class="units">${machineCards(v.units, t)}</div></section>`;
    if (this.page === "schedule")
      return scheduleEditor(
        v,
        this.day,
        this.draft,
        this.busy,
        this.dirty,
        t,
        this.copyDays,
      );
    if (this.page === "modes" || this.page === "profiles") {
      const kind = this.page === "modes" ? "mode" : "profile";
      return `<section><header><h2>${t[this.page]}</h2>${this.button("new-" + kind, kind === "mode" ? t.newMode : t.newProfile, "primary")}</header>${v[this.page].map((item) => `<div class="list-row"><div>${kind === "mode" ? `<span class="swatch" style="background:${color(item.color)}"></span>` : ""}<strong>${esc(item.name)}</strong>${kind === "profile" && item.id === v.building.profile_id ? ` <small>${t.active}</small>` : ""}</div><div class="actions"><button data-kind="${kind}" data-edit="${item.id}">${t.edit}</button><button class="danger" data-kind="${kind}" data-delete="${item.id}">${t.delete}</button></div></div>`).join("")}</section>`;
    }
    return `<section><p class="muted">${esc(t.cloudHistoryHelp)}</p><div class="toolbar"><label>${t.unit}<select id="history-unit">${this.options(
      v.units.map((u) => [u.id, u.name]),
      null,
    )}</select></label><label>${t.from}<input id="history-from" type="datetime-local"></label><label>${t.to}<input id="history-to" type="datetime-local"></label>${this.button("history", t.refresh)}</div>${this.renderHistory()}</section>`;
  }
  async loadMachineHistory(data) {
    this.history = null;
    this.historyUnavailable = false;
    try {
      this.history = await this.api("history", data);
    } catch {
      this.historyUnavailable = true;
    }
  }
  renderHistory() {
    const t = this.t,
      h = this.history;
    if (this.historyUnavailable)
      return `<p class="notice" role="status">${esc(t.cloudHistoryUnavailable)}</p>`;
    if (!h) return `<p class="muted">${t.chartEmpty}</p>`;
    const labels = h.labels || [],
      sets = h.datasets || [];
    return (
      sets
        .map((s) => {
          const values = (s.data || []).map((x) =>
            typeof x === "number" ? x : typeof x?.y === "number" ? x.y : null,
          );
          const valid = values.filter(Number.isFinite);
          if (!valid.length) return "";
          const low = valid.reduce((a, b) => Math.min(a, b), Infinity),
            high = valid.reduce((a, b) => Math.max(a, b), -Infinity),
            span = high - low || 1;
          const points = values
            .map((n, i) =>
              Number.isFinite(n)
                ? `${i === 0 || !Number.isFinite(values[i - 1]) ? "M" : "L"}${(i * 600) / Math.max(1, values.length - 1)},${140 - ((n - low) / span) * 120}`
                : "",
            )
            .join(" ");
          return `<h2 class="spaced">${esc(s.label)}</h2><svg viewBox="0 0 600 160" role="img" aria-label="${esc(s.label)}"><path d="${points}" fill="none" stroke="currentColor" stroke-width="2"/></svg><div class="table-wrap"><table><thead><tr><th>${t.time}</th><th>${t.value}</th></tr></thead><tbody>${values
            .slice(-200)
            .map(
              (n, i) =>
                `<tr><td>${esc(labels[Math.max(0, values.length - 200) + i])}</td><td>${esc(n ?? t.unknown)}</td></tr>`,
            )
            .join("")}</tbody></table></div>`;
        })
        .join("") || `<p>${t.chartEmpty}</p>`
    );
  }
  handle(action, element) {
    if (this.busy) return;
    const q = (s) => this.shadowRoot.querySelector(s);
    if (action === "automatic-schedule") {
      this.run(() => this.mutate("control", { schedule: true }));
    } else if (action.startsWith("automatic-")) {
      const data =
        action === "automatic-manual"
          ? { enabled: false }
          : action === "automatic-enable"
            ? { enabled: true }
            : automaticInputs(this.shadowRoot);
      this.run(async () => {
        this.automatic = await this.api("automatic", data);
        if (action !== "automatic-save") this.manualDraft = null;
        if (action === "automatic-save") this.automaticDraft = null;
        this.loadQualityHistory();
        this.notice = this.t.regulation.saved;
        this.failed = false;
      });
    } else if (action === "menu")
      this.dispatchEvent(
        new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }),
      );
    else if (action === "refresh") {
      if (this.confirmDiscard())
        this.run(() =>
          this.entryId
            ? this.loadView(this.view?.profile_id)
            : this.loadEntries(),
        );
    } else if (action === "apply") {
      let timer;
      try {
        timer = timerInputs(this.shadowRoot);
      } catch {
        this.notice = this.t.regulation.timerError;
        this.failed = true;
        this.render();
        return;
      }
      const data = {
        speed: Number(q("#speed").value),
        mode: q("#control-mode").value,
        bypass: q("#regulation-bypass").checked,
        ...timer,
      };
      this.run(() => this.mutate("control", data));
    } else if (action === "resume")
      this.run(() => this.mutate("control", { schedule: true }));
    else if (action === "activate") {
      if (this.confirmDiscard())
        this.run(() =>
          this.mutate("activate", { profile_id: this.view.profile_id }),
        );
    } else if (action === "add-row") {
      const row = addScheduleRow(this.draft);
      this.draft = sortedSchedule([...this.draft, row]);
      this.dirty = true;
      this.render();
      const index = this.draft.indexOf(row);
      q(`[data-schedule-${index ? "time" : "choice"}="${index}"]`)?.focus();
    } else if (action === "remove-row") {
      const index = Number(element.dataset.index);
      this.draft.splice(index, 1);
      this.dirty = true;
      this.render();
      q(
        `[data-schedule-choice="${Math.min(index, this.draft.length - 1)}"]`,
      )?.focus();
    } else if (action === "save-day" || action === "copy-day") {
      const copy = action === "copy-day";
      const days = copy ? [...this.copyDays] : [this.day];
      if (!days.length || scheduleIssue(this.view, days, this.draft)) return;
      const rows = sortedSchedule(this.draft);
      this.run(() => this.saveSchedule(days, rows, copy));
    } else if (action === "new-mode" || action === "new-profile")
      this.editor(action.slice(4));
    else if (action === "history") {
      const data = { unit_id: Number(q("#history-unit").value) },
        start = q("#history-from").value,
        end = q("#history-to").value;
      if (start || end) {
        data.start = start.replace("T", " ") + ":00";
        data.end = end.replace("T", " ") + ":00";
      }
      this.run(() => this.loadMachineHistory(data));
    } else if (action === "export") {
      const blob = new Blob(
        [
          JSON.stringify(
            {
              version: 1,
              profile_id: this.view.profile_id,
              profiles: this.view.profiles,
              modes: this.view.modes,
              week: this.view.week,
            },
            null,
            2,
          ),
        ],
        { type: "application/json" },
      );
      const url = URL.createObjectURL(blob),
        a = document.createElement("a");
      a.href = url;
      a.download = "wifimodule-programming.json";
      a.click();
      URL.revokeObjectURL(url);
    }
  }
  editor(kind, id) {
    const t = this.t,
      item = this.view[kind === "mode" ? "modes" : "profiles"].find(
        (x) => x.id === id,
      ) || { name: "", speed: 1, mode: "manual", bypass: 0, color: "#b4c7dc" };
    const dialog = document.createElement("dialog");
    dialog.innerHTML = `<form><h2>${kind === "mode" ? t.modes : t.profiles}</h2><label>${t.name}<input name="name" required maxlength="100" value="${esc(item.name)}"></label>${
      kind === "mode"
        ? `<div class="grid"><label>${t.speed}<select name="speed">${this.options(
            Array.from({ length: 9 }, (_, i) => [
              i,
              i === 0 ? t.off : i === 8 ? t.boost : String(i),
            ]),
            item.off ? 0 : item.boost ? 8 : item.speed,
          )}</select></label><label>${t.mode}<select name="mode">${this.options(
            [
              ["manual", t.manual],
              ["auto", t.auto],
            ],
            item.mode,
          )}</select></label><label>${t.color}<input name="color" type="color" value="${color(item.color)}"></label><label class="check"><input name="bypass" type="checkbox" ${item.bypass ? "checked" : ""}>${t.bypass}</label></div>`
        : ""
    }<div class="actions"><button type="submit" class="primary">${t.save}</button><button type="button" data-cancel>${t.cancel}</button></div></form>`;
    this.shadowRoot.append(dialog);
    dialog.querySelector("[data-cancel]").onclick = () => dialog.close();
    dialog.onclose = () => dialog.remove();
    dialog.querySelector("form").onsubmit = (e) => {
      e.preventDefault();
      if (kind === "mode" && id && !window.confirm(t.confirmEditMode)) return;
      const form = new FormData(e.target),
        data = { name: form.get("name") };
      if (id) data.id = id;
      if (kind === "mode")
        Object.assign(data, {
          speed: Number(form.get("speed")),
          mode: form.get("mode"),
          color: form.get("color"),
          bypass: form.has("bypass"),
        });
      dialog.close();
      this.run(() =>
        this.mutate(kind, { operation: id ? "edit" : "add", item: data }),
      );
    };
    dialog.showModal();
  }
}
customElements.define("jeremias-panel", JeremiasPanel);
