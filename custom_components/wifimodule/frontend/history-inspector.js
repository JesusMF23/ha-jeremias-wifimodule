// The plotted steps are pairs of start/end points. At a transition, the
// new value wins. At the end of an unavailable boundary, the old one expires.
function lastAtOrBefore(length, timeAt, time) {
  let low = 0;
  let high = length;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (timeAt(middle) <= time) low = middle + 1;
    else high = middle;
  }
  return low - 1;
}

export function historyInspector(series, start, end) {
  const changes = new Set();
  for (const { recordedTimes } of series)
    for (const time of recordedTimes) changes.add(time);
  if (!changes.size) changes.add(start);
  const times = [...changes].sort((a, b) => a - b);
  return {
    times,
    nearest(time) {
      const left = lastAtOrBefore(times.length, (i) => times[i], time);
      if (left < 0) return 0;
      if (
        left + 1 === times.length ||
        time - times[left] <= times[left + 1] - time
      )
        return left;
      return left + 1;
    },
    readings(index) {
      const time = times[index];
      return series.map(({ segments, endValue }) => {
        if (time === end) return endValue;
        const segment =
          segments[
            lastAtOrBefore(segments.length, (i) => segments[i][0][0], time)
          ];
        if (!segment) return null;
        const i =
          lastAtOrBefore(segment.length / 2, (n) => segment[n * 2][0], time) *
          2;
        const [start, value] = segment[i];
        return time === start || time < segment[i + 1][0] ? value : null;
      });
    },
  };
}

export function bindHistoryInspectors(root, charts, t, language) {
  const date = new Intl.DateTimeFormat(language, {
    dateStyle: "medium",
    timeStyle: "medium",
  });
  const number = new Intl.NumberFormat(language, { maximumFractionDigits: 6 });
  for (const model of charts) {
    if (!model.inspector) continue;
    const card = root.querySelector(`[data-quality-chart="${model.kind}"]`);
    if (!card) continue;
    const plot = card.querySelector("svg");
    const cursor = card.querySelector("[data-chart-cursor]");
    const dots = card.querySelectorAll("[data-chart-dot]");
    const input = card.querySelector("[data-chart-scrubber]");
    const details = card.querySelector("[data-chart-details]");
    const heading = details.querySelector("time");
    const values = details.querySelectorAll("dd");
    const { inspector, start, end, x, y } = model;

    const show = (index) => {
      const time = inspector.times[index];
      const horizontal = x(time);
      const label = date.format(time);
      const readings = inspector.readings(index);
      input.value = index;
      input.setAttribute(
        "aria-valuetext",
        [
          label,
          ...readings.map(
            (value, i) =>
              `${model.series[i].zone || model.series[i].name}: ${value == null ? t.unavailable : `${number.format(value)} ${model.series[i].unit || ""}`}`,
          ),
        ].join(" · "),
      );
      cursor.setAttribute("x1", horizontal);
      cursor.setAttribute("x2", horizontal);
      cursor.removeAttribute("hidden");
      heading.textContent = label;
      heading.dateTime = new Date(time).toISOString();
      readings.forEach((value, i) => {
        dots[i].toggleAttribute("hidden", value == null);
        if (value != null) {
          dots[i].setAttribute("cx", horizontal);
          dots[i].setAttribute("cy", y(value));
        }
        values[i].textContent =
          value == null
            ? t.unavailable
            : `${number.format(value)} ${model.series[i].unit || ""}`.trim();
      });
      details.hidden = false;
    };

    plot.onclick = (event) => {
      const transform = plot.getScreenCTM();
      if (!transform) return;
      const point = plot.createSVGPoint();
      point.x = event.clientX;
      point.y = event.clientY;
      const position = point.matrixTransform(transform.inverse());
      const fraction = (position.x - x(start)) / (x(end) - x(start));
      if (fraction < 0 || fraction > 1 || position.y < 0 || position.y > 178)
        return;
      show(inspector.nearest(start + fraction * (end - start)));
    };
    const showInput = () =>
      show(Math.min(Number(input.value), inspector.times.length - 1));
    input.onfocus = showInput;
    input.oninput = showInput;
    card.querySelector("[data-chart-close]").onclick = () => {
      input.focus();
      clear();
    };
    function clear() {
      details.hidden = true;
      cursor.setAttribute("hidden", "");
      for (const dot of dots) dot.setAttribute("hidden", "");
    }
    card.onkeydown = (event) => {
      if (event.key === "Escape" && !details.hidden) {
        event.stopPropagation();
        input.focus();
        clear();
      }
    };
  }
}
