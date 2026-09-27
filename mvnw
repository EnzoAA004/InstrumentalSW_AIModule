#!/bin/sh
set -eu

BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROPERTIES="$BASE_DIR/.mvn/wrapper/maven-wrapper.properties"
DISTRIBUTION_URL=$(sed -n 's/^distributionUrl=//p' "$PROPERTIES")

if [ -n "${MAVEN_HOME:-}" ] && [ -x "$MAVEN_HOME/bin/mvn" ]; then
  exec "$MAVEN_HOME/bin/mvn" "$@"
fi

if command -v mvn >/dev/null 2>&1; then
  exec mvn "$@"
fi

WRAPPER_HOME="${MAVEN_USER_HOME:-$HOME/.m2}/wrapper/dists/apache-maven-3.9.16"
MAVEN_BIN="$WRAPPER_HOME/apache-maven-3.9.16/bin/mvn"

if [ ! -x "$MAVEN_BIN" ]; then
  mkdir -p "$WRAPPER_HOME"
  ARCHIVE="$WRAPPER_HOME/apache-maven-3.9.16-bin.zip"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --silent --show-error "$DISTRIBUTION_URL" --output "$ARCHIVE"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$DISTRIBUTION_URL" -O "$ARCHIVE"
  else
    echo "Neither Maven, curl, nor wget is available." >&2
    exit 1
  fi
  if command -v unzip >/dev/null 2>&1; then
    unzip -q "$ARCHIVE" -d "$WRAPPER_HOME"
  else
    echo "unzip is required to install Maven." >&2
    exit 1
  fi
fi

exec "$MAVEN_BIN" "$@"
