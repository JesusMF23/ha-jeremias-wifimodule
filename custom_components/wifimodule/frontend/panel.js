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
const minute = (n) =>
  `${String(Math.floor(n / 60)).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`;
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
    this.entries = [];
    this.busy = false;
    this.dirty = false;
    this.view = null;
    this.notice = "";
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
    if (this._hass && !this.started) {
      this.started = true;
      this.run(() => this.loadEntries());
    }
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
    this.view = await this.api(
      "view",
      profile === undefined ? {} : { profile_id: Number(profile) },
    );
    this.history = null;
    this.dirty = false;
    this.resetDraft();
  }
  resetDraft() {
    this.draft = (this.view?.week?.[`d${this.day}`] || []).map((r) => ({
      time: r.time,
      mode: r.mode_id ?? r.mode,
    }));
  }
  async mutate(operation, data) {
    await this.api(operation, data);
    await this.loadView(
      operation === "profile" &&
        data.operation === "delete" &&
        data.item.id === this.view.profile_id
        ? undefined
        : this.view.profile_id,
    );
    this.notice = this.t.saved;
    this.failed = false;
  }
  confirmDiscard() {
    return !this.dirty || window.confirm(this.t.discard);
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
    this.shadowRoot.innerHTML = `<style>${styles}</style><main><header><button data-action="menu" aria-label="${t.menu}">☰</button><div><h1>${t.title}</h1><div class="muted">${t.subtitle}</div></div>${this.button("refresh", t.refresh)}</header>
    ${
      this.entries.length
        ? `<label>${t.building}<select id="installation" ${this.busy ? "disabled" : ""}>${this.options(
            this.entries.map((e) => [e.entry_id, e.name]),
            this.entryId,
          )}</select></label>`
        : `<p>${this.busy ? t.loading : t.empty}</p>`
    }
    ${this.notice ? `<div class="notice ${this.failed ? "error" : ""}" role="alert">${esc(this.notice)}</div>` : ""}
    ${
      v
        ? `<nav role="tablist">${["controls", "schedule", "modes", "profiles", "history"].map((p) => `<button role="tab" data-page="${p}" aria-selected="${this.page === p}" ${this.busy ? "disabled" : ""}>${t[p]}</button>`).join("")}</nav>
    ${this.busy ? `<p role="status">${t.loading}</p>` : ""}<div>${this.content()}</div>
    <footer class="muted">${t.cloud} · ${esc(v.timezone)}<p>${t.advanced}</p>${this.button("export", t.export)}</footer>`
        : ""
    }</main>`;
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
    const installation = this.shadowRoot.querySelector("#installation");
    if (installation)
      installation.onchange = () => {
        if (this.confirmDiscard()) {
          this.entryId = installation.value;
          this.view = null;
          this.run(() => this.loadView());
        } else this.render();
      };
    const profile = this.shadowRoot.querySelector("#profile");
    if (profile)
      profile.onchange = () => {
        if (this.confirmDiscard()) this.run(() => this.loadView(profile.value));
        else this.render();
      };
    const day = this.shadowRoot.querySelector("#day");
    if (day)
      day.onchange = () => {
        if (this.confirmDiscard()) {
          this.day = Number(day.value);
          this.dirty = false;
          this.resetDraft();
          this.render();
        } else this.render();
      };
    this.shadowRoot.querySelectorAll("[data-time]").forEach(
      (el) =>
        (el.oninput = () => {
          this.draft[Number(el.dataset.time)].time = parseTime(el.value);
          this.dirty = true;
        }),
    );
    this.shadowRoot.querySelectorAll("[data-mode]").forEach(
      (el) =>
        (el.onchange = () => {
          this.draft[Number(el.dataset.mode)].mode = Number(el.value);
          this.dirty = true;
        }),
    );
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
  content() {
    const t = this.t,
      v = this.view,
      b = v.building;
    if (this.page === "controls")
      return `<section><div class="status">${v.ready ? t.ready : t.waiting}</div><p>${t.scope} (${v.units.length})</p><div class="grid">
      <label>${t.speed}<select id="speed">${this.options(
        Array.from({ length: 9 }, (_, i) => [
          i,
          i === 0 ? t.off : i === 8 ? t.boost : String(i),
        ]),
        b.manual_speed ?? 1,
      )}</select></label>
      <label>${t.mode}<select id="control-mode">${this.options(
        [
          ["manual", t.manual],
          ["auto", t.auto],
        ],
        b.manual_mode ?? "manual",
      )}</select></label>
      <label>${t.duration}<input id="duration" type="number" min="0" max="10080" step="1" value="${v.duration}"></label>
      <label class="check"><input id="bypass" type="checkbox" ${b.manual_bypass ? "checked" : ""}>${t.bypass}</label></div>
      <small>${t.never}</small><div class="actions spaced">${this.button("apply", t.apply, "primary", !v.ready)}${this.button("resume", t.resume, "", !v.ready)}</div>
      <p class="muted">${b.manual_active ? `${t.manual} · ${esc(b.manual_override_until ?? t.never)}` : t.scheduleMode}</p></section>
      <div class="units">${v.units.map((u) => `<div class="card"><h2>${esc(u.name)}</h2><dl><dt>${t.power}</dt><dd>${u.values?.pwr === 1 ? t.on : u.values?.pwr === 0 ? t.off : t.unknown}</dd><dt>${t.speed}</dt><dd>${esc(u.values?.spe ?? t.unknown)}</dd><dt>${t.filter}</dt><dd>${esc(u.values?.fil ?? t.unknown)}</dd><dt>${t.errors}</dt><dd>${esc(u.values?.err ?? t.unknown)}</dd></dl><small>${t.lastComm}: ${esc(u.last_comm)}</small></div>`).join("")}</div>`;
    if (this.page === "schedule")
      return `<section><div class="toolbar"><label>${t.profile}<select id="profile">${this.options(
        v.profiles.map((p) => [p.id, p.name]),
        v.profile_id,
      )}</select></label><label>${t.day}<select id="day">${this.options(
        [1, 2, 3, 4, 5, 6, 0].map((d) => [d, t.days[d]]),
        this.day,
      )}</select></label>${this.button("activate", t.activate)}</div><p class="muted">${t.revision}</p>
      ${this.draft
        .map(
          (r, i) =>
            `<div class="schedule-row"><label>${t.start}<input type="time" data-time="${i}" value="${minute(r.time)}" ${i === 0 ? "disabled" : ""}></label><label>${t.mode}<select data-mode="${i}">${this.options(
              v.modes.map((m) => [m.id, m.name]),
              r.mode,
            )}</select></label><button data-action="remove-row" data-index="${i}" ${this.busy || i === 0 ? "disabled" : ""}>${t.remove}</button></div>`,
        )
        .join("")}
      <div class="actions">${this.button("add-row", t.add, "", !v.modes.length)}${this.button("save-day", t.saveDay, "primary", !this.draft.length)}</div>
      <div class="toolbar spaced"><label>${t.copy}<select id="copy-day">${this.options(
        [1, 2, 3, 4, 5, 6, 0]
          .filter((d) => d !== this.day)
          .map((d) => [d, t.days[d]]),
        null,
      )}</select></label>${this.button("copy-day", t.copyButton, "", !this.draft.length)}</div></section>`;
    if (this.page === "modes" || this.page === "profiles") {
      const kind = this.page === "modes" ? "mode" : "profile";
      return `<section><header><h2>${t[this.page]}</h2>${this.button("new-" + kind, kind === "mode" ? t.newMode : t.newProfile, "primary")}</header>${v[this.page].map((item) => `<div class="list-row"><div>${kind === "mode" ? `<span class="swatch" style="background:${color(item.color)}"></span>` : ""}<strong>${esc(item.name)}</strong>${kind === "profile" && item.id === b.profile_id ? ` <small>${t.active}</small>` : ""}</div><div class="actions"><button data-kind="${kind}" data-edit="${item.id}">${t.edit}</button><button class="danger" data-kind="${kind}" data-delete="${item.id}">${t.delete}</button></div></div>`).join("")}</section>`;
    }
    return `<section><div class="toolbar"><label>${t.unit}<select id="history-unit">${this.options(
      v.units.map((u) => [u.id, u.name]),
      null,
    )}</select></label><label>${t.from}<input id="history-from" type="datetime-local"></label><label>${t.to}<input id="history-to" type="datetime-local"></label>${this.button("history", t.refresh)}</div>${this.renderHistory()}</section>`;
  }
  renderHistory() {
    const t = this.t,
      h = this.history;
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
    if (action === "menu")
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
      const data = {
        speed: Number(q("#speed").value),
        mode: q("#control-mode").value,
        bypass: q("#bypass").checked,
        duration: Number(q("#duration").value),
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
      this.draft.push({
        time: this.draft.length
          ? Math.min(1439, this.draft.at(-1).time + 60)
          : 0,
        mode: this.view.modes[0].id,
      });
      this.dirty = true;
      this.render();
    } else if (action === "remove-row") {
      this.draft.splice(Number(element.dataset.index), 1);
      this.dirty = true;
      this.render();
    } else if (action === "save-day" || action === "copy-day") {
      const target =
        action === "copy-day" ? Number(q("#copy-day").value) : this.day;
      const rows = this.draft
        .map((r) => ({ ...r }))
        .sort((a, b) => a.time - b.time);
      this.run(() =>
        this.mutate("edit_day", {
          profile_id: this.view.profile_id,
          day: target,
          rows,
          revision: this.view.revision,
        }),
      );
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
      this.run(async () => {
        this.history = await this.api("history", data);
      });
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
