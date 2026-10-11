{ pkgs }: {
  # OpenCV (pulled in by the local OCR engine) needs these shared libraries on Linux.
  deps = [ pkgs.libGL pkgs.glib pkgs.zlib ];
}
