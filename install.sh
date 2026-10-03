#!/usr/bin/env sh
# Installs forge: one git checkout under ~/.forge, one `forge` shim on PATH.
#
#   sh install.sh                     install or update
#   FORGE_REF=v1.2 sh install.sh      pin a branch or tag
#   FORGE_HOME=/opt/forge sh install.sh
#   FORGE_BIN=/usr/local/bin sh install.sh
#
# Re-running it updates in place; it is the same operation as `forge self-update`.
# Nothing is written outside FORGE_HOME and FORGE_BIN, and nothing is compiled -
# forge is stdlib-only Python 3.
set -eu

REPO_HTTPS="${FORGE_REPO:-https://github.com/vstlmkh/forge.git}"
REPO_SSH="${FORGE_REPO_SSH:-git@github.com:vstlmkh/forge.git}"
FORGE_HOME="${FORGE_HOME:-$HOME/.forge}"
FORGE_BIN="${FORGE_BIN:-$HOME/.local/bin}"
FORGE_REF="${FORGE_REF:-master}"

say()  { printf '%s\n' "$*"; }
die()  { printf 'fatal: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

have git || die "git is required"
have python3 || die "python3 is required"
case "$(python3 -c 'import sys;print(sys.version_info>=(3,9))' 2>/dev/null)" in
  True) ;;
  *) die "python3 3.9 or newer is required" ;;
esac

if [ -d "$FORGE_HOME/.git" ]; then
  say "updating $FORGE_HOME"
  git -C "$FORGE_HOME" fetch --quiet origin "$FORGE_REF"
  git -C "$FORGE_HOME" checkout --quiet "$FORGE_REF"
  git -C "$FORGE_HOME" merge --ff-only --quiet "origin/$FORGE_REF" 2>/dev/null || true
elif [ -e "$FORGE_HOME" ]; then
  die "$FORGE_HOME exists and is not a git checkout - move it, or set FORGE_HOME"
else
  say "cloning into $FORGE_HOME"
  # a private repository answers over SSH but not over HTTPS without a token,
  # so try both rather than making the user pick
  git clone --quiet --branch "$FORGE_REF" "$REPO_HTTPS" "$FORGE_HOME" 2>/dev/null \
    || git clone --quiet --branch "$FORGE_REF" "$REPO_SSH" "$FORGE_HOME" \
    || die "could not clone $REPO_HTTPS or $REPO_SSH"
fi

[ -f "$FORGE_HOME/bin/forge" ] || die "$FORGE_HOME/bin/forge is missing - wrong repository?"
chmod +x "$FORGE_HOME/bin/forge"

mkdir -p "$FORGE_BIN"
ln -sf "$FORGE_HOME/bin/forge" "$FORGE_BIN/forge"
say "linked $FORGE_BIN/forge -> $FORGE_HOME/bin/forge"

say ""
say "forge $("$FORGE_HOME/bin/forge" version) installed"

case ":$PATH:" in
  *":$FORGE_BIN:"*)
    say ""
    say "next, in any project:"
    say "  forge detect          # what forge thinks the repository is made of"
    say "  forge init --auto     # install the harness from that, asking nothing"
    say "  forge init            # or describe it yourself"
    ;;
  *)
    say ""
    say "$FORGE_BIN is not on your PATH. Add it:"
    say "  echo 'export PATH=\"$FORGE_BIN:\$PATH\"' >> ~/.zshrc && exec zsh"
    say "or call it directly: $FORGE_HOME/bin/forge init --auto"
    ;;
esac
