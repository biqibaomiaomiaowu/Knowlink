import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';

abstract class HandoutVideoController {
  Future<void> initialize();

  Future<void> play();

  Future<void> pause();

  Future<void> seekTo(Duration position);

  Future<void> dispose();

  void addListener(VoidCallback listener);

  void removeListener(VoidCallback listener);

  Widget buildPlayer();

  bool get isInitialized;

  bool get isPlaying;

  Duration get position;

  Duration get duration;

  double get aspectRatio;
}

class VideoPlayerHandoutController implements HandoutVideoController {
  VideoPlayerHandoutController(Uri uri)
      : _controller = VideoPlayerController.networkUrl(uri);

  final VideoPlayerController _controller;

  @override
  Future<void> initialize() => _controller.initialize();

  @override
  Future<void> play() => _controller.play();

  @override
  Future<void> pause() => _controller.pause();

  @override
  Future<void> seekTo(Duration position) => _controller.seekTo(position);

  @override
  Future<void> dispose() => _controller.dispose();

  @override
  void addListener(VoidCallback listener) => _controller.addListener(listener);

  @override
  void removeListener(VoidCallback listener) =>
      _controller.removeListener(listener);

  @override
  Widget buildPlayer() => VideoPlayer(_controller);

  @override
  bool get isInitialized => _controller.value.isInitialized;

  @override
  bool get isPlaying => _controller.value.isPlaying;

  @override
  Duration get position => _controller.value.position;

  @override
  Duration get duration => _controller.value.duration;

  @override
  double get aspectRatio => _controller.value.aspectRatio;
}

typedef HandoutVideoControllerFactory = HandoutVideoController Function(
    Uri uri);

final handoutVideoControllerFactoryProvider =
    Provider<HandoutVideoControllerFactory>(
  (ref) => VideoPlayerHandoutController.new,
);
