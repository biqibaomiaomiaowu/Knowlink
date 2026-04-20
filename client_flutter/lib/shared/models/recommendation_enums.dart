enum SelfLevel {
  beginner,
  intermediate,
  advanced,
}

enum PreferredStyle {
  balanced,
  exam,
  detailed,
  quick,
}

enum ResourceType {
  mp4,
  pdf,
  pptx,
  docx,
  srt,
}

String dateTimeToOffsetIsoString(DateTime value) {
  final base = value.toIso8601String();
  if (value.isUtc) {
    return base;
  }

  final offset = value.timeZoneOffset;
  final sign = offset.isNegative ? '-' : '+';
  final hours = offset.inHours.abs().toString().padLeft(2, '0');
  final minutes = (offset.inMinutes.abs() % 60).toString().padLeft(2, '0');
  return '$base$sign$hours:$minutes';
}
