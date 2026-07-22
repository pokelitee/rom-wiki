const DISPLAY_NAMES = Object.freeze({
  "poke-balls": "Poké Balls",
  "poke-radar": "Poké Radar",
  "tm-hm": "TM / HM",
  "vs-recorder": "Vs. Recorder",
  "vs-seeker": "Vs. Seeker",
  "trainer-ai-item": "Trainer AI item",
});

export function displayFilter(key, value) {
  if (key === "double_battle") return value === true ? "Double" : "Single";
  if (key === "linked") return value === true ? "Mapped" : "Unlinked";
  if (key === "referenced") return value === true ? "Referenced" : "Unreferenced";
  if (key === "access_methods" && value === "machine") return "TM / HM";
  return title(value);
}

export function title(value) {
  const normalized = String(value);
  return DISPLAY_NAMES[normalized]
    || normalized.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
