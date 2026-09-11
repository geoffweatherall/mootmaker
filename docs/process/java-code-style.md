# Java code style

Java in this project is formatted by **[google-java-format](https://github.com/google/google-java-format)
in unmodified Google style**, and linted by **Google's Checkstyle ruleset**, with a short list of
recorded exceptions.

The point of adopting someone else's standard is that it settles arguments without anyone having to
win them. So the rule is: we take Google's, we do not tune it to taste, and where we genuinely cannot
follow it the deviation is written down with its reason rather than quietly applied.

## Setting up a machine

```bash
./tools/install-workspace-config.sh --force
```

That links the versioned VS Code settings into the workspace and installs the extensions they depend
on. There are no manual steps, and nothing to remember on a second machine — see
[Why the editor needs configuring at all](#why-the-editor-needs-configuring-at-all).

## What runs

| Concern | Tool | Fix it with |
|---|---|---|
| Formatting | Spotless + google-java-format | `mvn -f impl/pom.xml spotless:apply` |
| Style rules | Checkstyle, `google_checks.xml` | by hand |
| Unused imports, locals, params | Eclipse compiler (ecj) | `./lint-java.sh` reports; mostly `spotless:apply` fixes |

All three run in each repository's `code-style` PR check. Applies to **mootmaker-api** and
**mootmaker-demo-data**, the two repositories with Java in them.

## The decisions, and why

### Google style, not AOSP or Palantir

Palantir was the closest fit on taste — 4-space indent, 120 columns, much like what this codebase
already looked like. It is **disqualified**: it cannot parse Java 25 module imports, failing with
`Expected ; after import` on all 41 files that use one.

AOSP is google-java-format with 4-space indentation, and would have been a far smaller diff (2,956
lines against 7,424). It was rejected because `google_checks.xml` hard-codes 2-space indentation, so
AOSP formatting plus Google's linter contradict each other. Taking Google whole means the two halves
agree with no overrides.

The reformat cost ~7,400 lines across 99 files, once, mechanically.

### The editor must run google-java-format, not VS Code's built-in formatter

VS Code's Java support is Eclipse JDT, which is a **different formatter**. Google publishes an
Eclipse profile intended to approximate their style; measured against real google-java-format output
on this codebase it **diverges on 47 of 49 files, 2,708 lines**, mostly javadoc wrapping.

Left to itself, the editor would reformat on save into something CI rejects. So Java formatting is
handed to an extension that runs google-java-format itself.

### `jar-file` mode, never `native-binary`

This one bites silently, and it is the extension's default, so it has to be overridden explicitly.

google-java-format ships a native binary. It **cannot parse Java 25 module imports**:

```
error: '.' expected
import module java.base;
```

It fails that way on every file using one and leaves them unformatted, reporting nothing in the
editor. The jar running on JDK 25 handles them correctly and produces output byte-identical to the
Maven build.

**If formatting silently stops working on most files, check this setting first.**

### `reflowLongStrings` is on

google-java-format's command line runs a string-wrapping pass that its library API does not. The
editor extension runs the command line; Spotless calls the library. Without this setting the editor
rewraps long string literals and the build then rejects the result — a fight on every save.

With it on, Spotless output is byte-identical to the command line's. Verified across all 49 main
sources.

### The version is pinned in three places

`google-java-format.version` in both `impl/pom.xml` files, and
`java.format.settings.google.version` in `workspace-config/vscode-settings.json`, must all be the
same number. The extension's own default is `latest`, which drifts away from the build the day Google
ships a release. **Bumping the formatter means bumping all three together.**

### Checkstyle has to be told to fail

`google_checks.xml` reports everything at `warning` severity, and maven-checkstyle-plugin only fails
on errors. Configured the obvious way it prints thousands of findings and still reports
`BUILD SUCCESS`. `violationSeverity=warning` is what makes it a gate rather than decoration.

### ecj is there for what Google's tooling misses

javac has no unused-import diagnostic at all, which is why unused imports accumulated here unnoticed.
google-java-format removes ordinary ones — but not an unused `import module`, and `google_checks.xml`
contains no `UnusedImports` rule whatsoever. So Google's stack, complete as it is, would not have
caught the thing that prompted this work.

`lint-java.sh` runs the Eclipse compiler in diagnose-only mode. That is the same compiler the editor
uses, so CI sees what the editor already showed.

## Deviations from Google

In `config/checkstyle-suppressions.xml` in each repository, kept there rather than by editing
`google_checks.xml`, so the answer to "what do we differ on?" is a short file rather than a fork of
108 modules nobody will re-compare when Google updates it.

| Rule | Scope | Why |
|---|---|---|
| `MissingJavadocMethod`, `MissingJavadocType`, `SummaryJavadoc` | everywhere | A deliberate call: this codebase explains itself where the reasoning is non-obvious and does not want a javadoc block on every accessor. Requiring one produces filler restating the signature. |
| `CustomImportOrder` | everywhere | **Cannot parse Java 25.** With static imports and an `import module` in the same file it loses the group boundaries and demands blank lines that are already present. Nothing is lost: google-java-format sorts imports itself and `spotless:check` fails if they drift. |
| `AbbreviationAsWordInName`, `GoogleMethodName` | **test sources only** | Test methods are named as sentences — `writesTheFirstVersionOfADay` — and Google's rules read the article "A" before a capitalised word as an abbreviation. Production code still has to satisfy both. |

## Why the editor needs configuring at all

The directory holding the checkouts is inside no git repository, so anything written to its
`.vscode/` folder is unversioned and does not exist on another machine. The versioned copy therefore
lives in `workspace-config/vscode-settings.json` and is symlinked into place — the same pattern as
`.claude/settings.json` and the `CLAUDE.md → AGENTS.md` symlinks.

Edit the versioned file, never the linked one.
