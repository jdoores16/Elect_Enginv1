
{ pkgs }:
{
  deps = [
    pkgs.python311Full
    pkgs.python311Packages.pip

    # Helpful for packages that compile or link
    pkgs.pkgconfig
    pkgs.libffi
    pkgs.openssl
    pkgs.zlib
    pkgs.git
  ];
}