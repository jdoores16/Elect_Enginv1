{ pkgs }:
{
  deps = [
    pkgs.python311Full
    pkgs.python311Packages.pip
    pkgs.pkgconfig
    pkgs.libffi
    pkgs.openssl
    pkgs.zlib
    pkgs.git
  ];
}
