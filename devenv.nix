{
  lib,
  pkgs,
  ...
}:

{
  # The media tools the analysis shells out to. The Dockerfile installs the
  # same ones from Debian; a test that passes here and fails in the image is
  # usually a version difference between the two.
  packages = with pkgs; [
    chromaprint
    ffmpeg
    gh
    git
    jq
    skopeo
  ];

  languages.python = {
    enable = true;
    package = pkgs.python313;
    venv.enable = true;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  # uv's own interpreters are dynamically linked against an FHS layout and do
  # not run on NixOS.
  env.UV_PYTHON_DOWNLOADS = "never";

  # treefmt runs on commit, under `devenv test` and by hand: entering the shell
  # does not rewrite files.
  tasks."devenv:treefmt:run".before = lib.mkForce [ ];

  treefmt = {
    enable = true;

    config = {
      settings.global.excludes = [
        "devenv.lock"
        "uv.lock"
        "LICENSE"
        # Written by release-please.
        "CHANGELOG.md"
      ];

      programs = {
        deadnix.enable = true;
        jsonfmt.enable = true;
        nixfmt.enable = true;
        ruff-format.enable = true;
        statix.enable = true;
        taplo.enable = true;
        yamlfmt.enable = true;
      };

      # Leave blank lines as written, and do not re-fold `>` scalars.
      programs.yamlfmt.settings.formatter = {
        retain_line_breaks = true;
        scan_folded_as_literal = true;
      };

      settings.formatter = {
        deadnix.priority = 0;
        statix.priority = 0;
        nixfmt.priority = 1;

        # The types no formatter above covers: Markdown, the Dockerfile, .envrc.
        whitespace = {
          command = lib.getExe (
            pkgs.writeShellApplication {
              name = "whitespace";
              runtimeInputs = with pkgs; [
                coreutils
                diffutils
                gnused
              ];
              text = ''
                for file in "$@"; do
                  tmp="$(mktemp)"
                  printf '%s\n' "$(sed -e 's/[[:space:]]*$//' "$file")" > "$tmp"
                  # Only when something changed, so --fail-on-change stays honest.
                  cmp -s "$tmp" "$file" || cat "$tmp" > "$file"
                  rm -f "$tmp"
                done
              '';
            }
          );
          includes = [ "*" ];
          priority = 2;
        };
      };
    };
  };

  git-hooks.hooks = {
    ruff.enable = true;
    treefmt.enable = true;

    # release-please derives every version and changelog entry from these.
    convco.enable = true;

    pytest = {
      enable = true;
      name = "pytest";
      entry = "uv run --locked pytest -q";
      files = "\\.py$|^pyproject\\.toml$|^uv\\.lock$";
      pass_filenames = false;
    };
  };
}
