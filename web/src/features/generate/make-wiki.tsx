import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { FileUp, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { Button } from "../../components/ui/button";
import { wikiFromBundle } from "../../generate/bundle";
import { importWiki, storeWiki } from "../../generate/library";
import { generateWiki } from "../../generate/run";
import type { LocalWiki } from "../../generate/store";

type State =
  | { step: "idle" }
  | { step: "working"; started: number; messages: string[] }
  | { step: "done"; wiki: LocalWiki }
  | { step: "error"; message: string };

export function MakeWiki({
  onLibraryChange,
}: {
  onLibraryChange: () => Promise<void>;
}) {
  const [rom, setRom] = useState<File>();
  const [baseRom, setBaseRom] = useState<File>();
  const [state, setState] = useState<State>({ step: "idle" });
  const working = state.step === "working";

  async function finish(wiki: LocalWiki) {
    await onLibraryChange();
    setState({ step: "done", wiki });
  }

  async function generate() {
    if (!rom) return;
    setState({ step: "working", started: Date.now(), messages: [] });
    try {
      const { files, generator } = await generateWiki(rom, baseRom, (message) =>
        setState((current) =>
          current.step === "working"
            ? { ...current, messages: [...current.messages, message].slice(-50) }
            : current,
        ),
      );
      const { wiki, files: stored } = wikiFromBundle(files, generator);
      await storeWiki(wiki, stored);
      await finish(wiki);
    } catch (error) {
      setState({ step: "error", message: messageOf(error) });
    }
  }

  async function importFile(file: File) {
    setState({ step: "working", started: Date.now(), messages: [] });
    try {
      await finish(await importWiki(file));
    } catch (error) {
      setState({ step: "error", message: messageOf(error) });
    }
  }

  return (
    <>
      <p className="eyebrow">Your own ROM</p>
      <h1>Make a wiki</h1>
      <p className="lead">
        Build a complete wiki from your copy of a supported game or ROM hack:
        Pokémon, moves, items, trainers, encounters, and locations, read from
        the ROM itself.
      </p>
      <div className="notice">
        <ShieldCheck size={20} />
        <div>
          <strong>Your ROM stays on this device</strong>
          <p>
            The wiki is built in your browser and saved here. Nothing you
            choose is uploaded.
          </p>
        </div>
      </div>
      <section className="panel make-wiki-form" aria-labelledby="make-heading">
        <h2 id="make-heading">Generate from a ROM</h2>
        <FileField
          label="ROM"
          accept=".gba,.nds"
          disabled={working}
          onFile={setRom}
          hint="A Game Boy Advance (.gba) or Nintendo DS (.nds) image of a Generation III–V game, or a hack of one."
        />
        <FileField
          label="Original game (optional)"
          accept=".gba,.nds"
          disabled={working}
          onFile={setBaseRom}
          hint="For a ROM hack, add the unmodified game it was made from to list every change the hack makes."
        />
        <Button disabled={!rom || working} onClick={generate}>
          <Sparkles size={15} aria-hidden="true" />
          Generate wiki
        </Button>
        <p className="muted">
          Generation usually takes under a minute, plus a few seconds the
          first time to load the generator. Keep this tab open until it
          finishes.
        </p>
      </section>
      <section className="panel make-wiki-form" aria-labelledby="import-heading">
        <h2 id="import-heading">Import a saved wiki</h2>
        <FileField
          label="Wiki file"
          accept=".gz,application/gzip"
          disabled={working}
          onFile={(file) => {
            if (file) importFile(file);
          }}
          hint="A wiki exported from the library, in this or another browser."
        />
      </section>
      <Status state={state} />
    </>
  );
}

function FileField({
  label,
  hint,
  accept,
  disabled,
  onFile,
}: {
  label: string;
  hint: string;
  accept: string;
  disabled: boolean;
  onFile: (file: File | undefined) => void;
}) {
  const id = useId();
  return (
    <div className="file-field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="file"
        accept={accept}
        disabled={disabled}
        aria-describedby={`${id}-hint`}
        onChange={(event) => onFile(event.target.files?.[0])}
      />
      <small id={`${id}-hint`} className="muted">
        {hint}
      </small>
    </div>
  );
}

function Status({ state }: { state: State }) {
  if (state.step === "working") return <Progress state={state} />;
  if (state.step === "error")
    return (
      <div className="notice notice-error" role="alert">
        <TriangleAlert size={20} />
        <div>
          <strong>The wiki could not be made</strong>
          <p>{state.message}</p>
        </div>
      </div>
    );
  if (state.step === "done")
    return (
      <div className="notice" role="status">
        <FileUp size={20} />
        <div>
          <strong>{state.wiki.game.name} is ready</strong>
          {!state.wiki.verified && (
            <p>
              This ROM isn't one this site knows, so it was read as the game
              its header names. Check the data before relying on it.
            </p>
          )}
          <p>
            <Link to={`/${state.wiki.id}`}>Open the wiki</Link> · It's also in
            your library.
          </p>
        </div>
      </div>
    );
  return null;
}

function Progress({
  state,
}: {
  state: Extract<State, { step: "working" }>;
}) {
  const [now, setNow] = useState(() => Date.now());
  const log = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    log.current?.lastElementChild?.scrollIntoView({ block: "nearest" });
  }, [state.messages.length]);
  const seconds = Math.max(0, Math.round((now - state.started) / 1000));
  return (
    <section className="panel generate-progress" aria-live="polite">
      <p role="status">
        <strong>{state.messages.at(-1) ?? "Starting…"}</strong>{" "}
        <span className="muted">{seconds}s</span>
      </p>
      <ol ref={log} className="generate-log">
        {state.messages.map((message, index) => (
          <li key={index}>{message}</li>
        ))}
      </ol>
    </section>
  );
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
