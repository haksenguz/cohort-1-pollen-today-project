/**
 * Model output as semantic HTML (bugs.md C2).
 *
 * The model writes markdown: `**bold**`, bullet lists, line breaks. Rendering
 * that as literal characters made the chat read like a log file, so it is
 * parsed here.
 *
 * Three rules keep model text from becoming an attack surface:
 *
 * 1. The model never gets raw HTML. react-markdown has no `rehype-raw` in the
 *    pipeline, so a `<script>` payload in a reply stays text.
 * 2. Links open in a new tab with `rel="noopener noreferrer"`, and only a
 *    short list of schemes survives. `javascript:` and friends are dropped.
 * 3. Images are not loaded. A model cannot ask the phone to fetch a URL.
 */
import ReactMarkdown, { type Components } from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

/** Schemes a link in model output is allowed to keep. */
const SAFE_SCHEMES = new Set(["http:", "https:", "mailto:", "tel:"]);

/**
 * Removes the characters a browser ignores when it reads a URL scheme. A tab
 * inside `java<TAB>script:alert(1)` runs as `javascript:`, so the scheme
 * check has to see the cleaned URL.
 */
function stripUrlNoise(url: string): string {
  let cleaned = "";
  for (const char of url) {
    const code = char.codePointAt(0) ?? 0;
    if (code <= 0x20 || code === 0x7f) continue;
    cleaned += char;
  }
  return cleaned;
}

/**
 * Returns the URL when it is safe to put in an href, and an empty string when
 * it is not. Callers treat an empty string as "render the link text, no link".
 */
function safeModelUrl(url: string): string {
  const probe = stripUrlNoise(url);
  if (probe === "") return "";
  // Root-relative, protocol-relative and fragment URLs inherit the page
  // scheme, which is http(s) here.
  if (probe.startsWith("/") || probe.startsWith("#")) return url;
  const colon = probe.indexOf(":");
  if (colon === -1) return url;
  // A colon after a slash belongs to the path, not to a scheme.
  const boundary = probe.search(/[/?#]/);
  if (boundary !== -1 && boundary < colon) return url;
  const scheme = probe.slice(0, colon).toLowerCase();
  // Anything that is not a well formed scheme is refused rather than guessed
  // at. A browser would not run it either, but the link should not be there.
  if (!/^[a-z][a-z0-9+.-]*$/.test(scheme)) return "";
  return SAFE_SCHEMES.has(`${scheme}:`) ? url : "";
}

const components: Components = {
  a({ href, children, ...props }) {
    // urlTransform already emptied a refused URL, so an empty href means the
    // link was not safe. The words stay on screen, the link does not.
    if (!href) return <span {...props}>{children}</span>;
    return (
      <a {...props} href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  },
  img({ alt }) {
    // The image is not fetched. Its description still is, because it is text
    // the model wrote and the user may need it.
    return alt ? <span className="aui-prose-alt">{alt}</span> : null;
  },
};

export interface MarkdownProps {
  text: string;
}

/** Renders one message body. Plain text passes through unchanged. */
export function Markdown({ text }: MarkdownProps) {
  return (
    <div className="aui-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        urlTransform={(url) => safeModelUrl(url)}
        components={components}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
