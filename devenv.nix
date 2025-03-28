{
  pkgs,
  lib,
  config,
  inputs,
  ...
}: {
  languages.python.enable = true;
  languages.python.version = "3.13.1";
}
