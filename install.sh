#!/usr/bin/env sh
# Installs forge: one git checkout under ~/.forge, one `forge` shim on PATH.
#
#   sh install.sh                      install or update
#   FORGE_REF=v1.2 sh install.sh       pin a branch or tag
#   FORGE_REPO=git@host:me/forge.git sh install.sh    clone from somewhere else
#   FORGE_HOME=/opt/forge FORGE_BIN=/usr/local/bin sh install.sh
#
# Re-running it updates in place; that is the same operation as
# `forge self-update`. Nothing is written outside FORGE_HOME and FORGE_BIN and
# nothing is compiled - forge is stdlib-only Python 3.
set -eu

SLUG="${FORGE_SLUG:-vstlmkh/forge}"
REPO_HTTPS="https://github.com/$SLUG.git"
REPO_SSH="git@github.com:$SLUG.git"
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

# Every URL worth trying, best first. A private repository answers over https
# only if a credential helper holds a token, and over ssh only for the key that
# has access - on a machine with several GitHub accounts that key is usually
# reached through a Host alias in ~/.ssh/config, never through plain
# git@github.com. So try them all rather than making the user work it out.
candidates() {
  if [ -n "${FORGE_REPO:-}" ]; then
    printf '%s\n' "$FORGE_REPO"
    return 0
  fi
  printf '%s\n%s\n' "$REPO_HTTPS" "$REPO_SSH"
  [ -f "$HOME/.ssh/config" ] || return 0
  awk 'tolower($1) == "host" { for (i = 2; i <= NF; i++) print $i }' "$HOME/.ssh/config" |
  while read -r alias; do
    case "$alias" in
      *[*?]*|github.com) continue ;;
    esac
    if ssh -G "$alias" 2>/dev/null | grep -qi '^hostname github\.com$'; then
      printf 'git@%s:%s.git\n' "$alias" "$SLUG"
    fi
  done
}

# GIT_TERMINAL_PROMPT=0: an https clone of a private repo would otherwise stop
# and ask for a username, which is a hang when this is piped into sh.
try_clone() {
  GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND="ssh -o BatchMode=yes" \
    git clone --quiet --branch "$FORGE_REF" "$1" "$FORGE_HOME" 2>/dev/null
}

if [ -d "$FORGE_HOME/.git" ]; then
  say "updating $FORGE_HOME"
  git -C "$FORGE_HOME" fetch --quiet origin "$FORGE_REF"
  git -C "$FORGE_HOME" checkout --quiet "$FORGE_REF"
  git -C "$FORGE_HOME" merge --ff-only --quiet "origin/$FORGE_REF" 2>/dev/null || true
elif [ -e "$FORGE_HOME" ]; then
  die "$FORGE_HOME exists and is not a git checkout - move it, or set FORGE_HOME"
else
  say "cloning into $FORGE_HOME"
  CLONED=""
  TRIED=""
  for url in $(candidates); do
    TRIED="$TRIED
  $url"
    if try_clone "$url"; then
      CLONED="$url"
      say "  cloned from $url"
      break
    fi
    rm -rf "$FORGE_HOME"
  done
  [ -n "$CLONED" ] || die "could not clone $SLUG. Tried:$TRIED

If the repository is private, make sure one of these can reach it - a token in
your git credential helper for https, or an ssh key with access - or clone it
yourself and point the installer at it:
  FORGE_REPO=<url> sh install.sh"
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
