import { escapeText as e } from "./automatic.js";

export async function saveDeviceName(hass, deviceId, value) {
  const name = value.trim();
  if (!deviceId || !name || name.length > 100)
    throw Error("Invalid device name");
  await hass.callWS({
    type: "config/device_registry/update",
    device_id: deviceId,
    name_by_user: name,
  });
}

// Kept outside the periodically replaced reading cards so typing survives polling.
export function editDeviceName(root, hass, sensor, t, onSaved) {
  if (root.querySelector("dialog[open]")) return;
  const dialog = document.createElement("dialog");
  dialog.setAttribute("aria-labelledby", "sensor-name-title");
  dialog.innerHTML = `<form><h2 id="sensor-name-title">${e(t.editName)}</h2><p id="sensor-name-help" class="muted">${e(t.nameHelp)}</p><label>${e(t.sensorName)}<input name="device_name" required maxlength="100" value="${e(sensor.zone)}" aria-describedby="sensor-name-help" autocomplete="off"></label><p role="alert" class="error" hidden></p><div class="actions"><button type="button" data-cancel>${e(t.nameCancel)}</button><button type="submit" class="primary">${e(t.nameSave)}</button></div></form>`;
  root.append(dialog);
  const input = dialog.querySelector("input");
  const save = dialog.querySelector('[type="submit"]');
  const cancel = dialog.querySelector("[data-cancel]");
  const error = dialog.querySelector('[role="alert"]');
  let saving = false;
  const validate = () => {
    save.disabled = saving || !input.value.trim();
  };
  input.oninput = validate;
  cancel.onclick = () => dialog.close();
  dialog.oncancel = (event) => {
    if (saving) event.preventDefault();
  };
  dialog.onclose = () => {
    dialog.remove();
    [...root.querySelectorAll("[data-rename-device]")]
      .find((button) => button.dataset.renameDevice === sensor.device_id)
      ?.focus();
  };
  dialog.querySelector("form").onsubmit = async (event) => {
    event.preventDefault();
    if (
      saving ||
      !input.value.trim() ||
      !dialog.querySelector("form").reportValidity()
    )
      return;
    saving = true;
    input.disabled = cancel.disabled = save.disabled = true;
    save.textContent = t.nameSaving;
    error.hidden = true;
    try {
      await saveDeviceName(hass, sensor.device_id, input.value);
      await onSaved();
      dialog.close();
    } catch {
      error.textContent = t.nameError;
      error.hidden = false;
      saving = false;
      input.disabled = cancel.disabled = false;
      save.textContent = t.nameSave;
      validate();
      input.focus();
    }
  };
  dialog.showModal();
  input.focus();
  input.select();
  validate();
}
