# mcn_ui — MCN Flutter UI Component Library

Native Flutter component library with default UI/UX components mirroring `@mcn/ui` (React), designed for internal teams and learners building Flutter mobile apps with MCN.

## Features
- 🎨 **MCN Design Tokens**: `MCNTheme.light()` & `MCNTheme.dark()`
- 🧩 **Standard Components**: `MCNButton`, `MCNInput`, `MCNBadge`, `MCNCard`, `MCNStat`
- 🤖 **AI Primitives**: `MCNAIPrompt`, `MCNStreamingText`, `MCNOutputLog`

## Usage in Generated Flutter Apps

```dart
import 'package:flutter/material.dart';
import 'package:mcn_ui/mcn_ui.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      theme: MCNTheme.light(),
      darkTheme: MCNTheme.dark(),
      home: Scaffold(
        appBar: AppBar(title: const Text('MCN App')),
        body: Center(
          child: MCNCard(
            title: 'Welcome',
            description: 'Built with MCN Mobile Generator',
            child: MCNButton(
              label: 'Get Started',
              variant: MCNButtonVariant.primary,
              onPressed: () {},
            ),
          ),
        ),
      ),
    );
  }
}
```
