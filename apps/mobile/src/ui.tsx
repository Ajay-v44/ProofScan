import { colors, radii } from "@proofscan/design-tokens";
import { Pressable, ScrollView, StyleSheet, Text, View, type ViewProps } from "react-native";
import type { ReactNode } from "react";
import { SafeAreaView } from "react-native-safe-area-context";

export const styles = StyleSheet.create({
  screen: { backgroundColor: colors.canvas, flex: 1 },
  layout: { width: "100%", maxWidth: 660, alignSelf: "center", paddingHorizontal: 16, paddingTop: 18, gap: 14, paddingBottom: 32 },
  panel: { backgroundColor: colors.surface, padding: 16, borderRadius: radii.card, borderWidth: 1, borderColor: colors.line, gap: 12 },
  intro: { paddingVertical: 8, gap: 8 },
  title: { fontSize: 30, fontWeight: "800", letterSpacing: -0.9, color: colors.ink },
  heading: { fontSize: 20, fontWeight: "800", letterSpacing: -0.35, color: colors.ink },
  fieldLabel: { fontSize: 15, fontWeight: "700", color: colors.ink },
  text: { fontSize: 16, lineHeight: 24, color: colors.muted },
  input: { borderWidth: 1, borderColor: colors.border, padding: 12, borderRadius: radii.control, minHeight: 50, fontSize: 16, color: colors.ink, backgroundColor: colors.surface },
  button: { padding: 12, minHeight: 48, borderWidth: 1, borderColor: colors.brand, borderRadius: radii.control, backgroundColor: colors.brand, justifyContent: "center", alignItems: "center" },
  outline: { backgroundColor: colors.surface, borderColor: colors.border },
  label: { fontSize: 15, color: colors.surface, textAlign: "center", fontWeight: "700" },
  outlineLabel: { color: colors.brand },
  error: { color: colors.danger, backgroundColor: colors.dangerTint, padding: 10, borderRadius: radii.control, fontSize: 15, lineHeight: 22 },
  progress: { padding: 14, gap: 8, borderWidth: 1, borderColor: colors.line,
    borderRadius: radii.card, backgroundColor: colors.surface },
  progressText: { fontSize: 14, color: colors.brand, fontWeight: "700" },
  track: { flexDirection: "row", gap: 6 },
  segment: { flex: 1, height: 5, borderRadius: 4, backgroundColor: colors.line },
  complete: { backgroundColor: colors.brand },
});

export function Screen({ children }: { children: ReactNode }) {
  return <SafeAreaView style={styles.screen} edges={["bottom", "left", "right"]}>
    <ScrollView contentContainerStyle={styles.layout} keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets>
      {children}
    </ScrollView>
  </SafeAreaView>;
}
export function Panel({ style, ...props }: ViewProps) {
  return <View {...props} style={[styles.panel, style]} />;
}
export function Action({ children, onPress, disabled, quiet }: { children: string; onPress: () => void; disabled?: boolean; quiet?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
    style={({ pressed }) => [styles.button, quiet && styles.outline, (pressed || disabled) && { opacity: 0.65 }]}>
    <Text style={[styles.label, quiet && styles.outlineLabel]}>{children}</Text>
  </Pressable>;
}
export function Failure({ error }: { error: unknown }) {
  return error ? <Text accessibilityRole="alert" style={styles.error}>{error instanceof Error ? error.message : String(error)}</Text> : null;
}

export function StepRail({ steps, current }: { steps: string[]; current: number }) {
  const description = `Step ${current + 1} of ${steps.length} · ${steps[current]}`;
  return <View accessible accessibilityRole="progressbar" accessibilityLabel="Verification progress"
    accessibilityValue={{ min: 1, now: current + 1, max: steps.length, text: description }} style={styles.progress}>
    <Text style={styles.progressText}>{description}</Text>
    <View style={styles.track}>
      {steps.map((label, index) => <View key={label} style={[styles.segment, index <= current && styles.complete]} />)}
    </View>
  </View>;
}
