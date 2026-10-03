import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract interface class LocalVault {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

/// Production vault. Android/iOS delegate encryption and key custody to the
/// platform-backed secure storage implementation.
class SecureLocalVault implements LocalVault {
  SecureLocalVault({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);

  @override
  Future<void> delete(String key) => _storage.delete(key: key);
}

/// Deterministic test vault. It is never selected by production main().
class MemoryLocalVault implements LocalVault {
  MemoryLocalVault([Map<String, String>? seed])
      : _values = Map<String, String>.from(seed ?? const {});

  final Map<String, String> _values;

  Map<String, String> get snapshot => Map.unmodifiable(_values);

  @override
  Future<String?> read(String key) async => _values[key];

  @override
  Future<void> write(String key, String value) async {
    _values[key] = value;
  }

  @override
  Future<void> delete(String key) async {
    _values.remove(key);
  }
}

class LocalPersistenceException implements Exception {
  const LocalPersistenceException(this.code);
  final String code;

  @override
  String toString() => 'QROS_LOCAL_PERSISTENCE_ERROR:$code';
}

/// One transaction completes (including in-memory commit) before the next starts.
/// A failed operation must not poison subsequent retries.
class LocalMutationQueue {
  Future<void> _tail = Future<void>.value();
  Future<T> run<T>(Future<T> Function() operation) {
    final result = _tail.then((_) => operation());
    _tail = result.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return result;
  }
}
