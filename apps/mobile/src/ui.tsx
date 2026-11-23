import { colors, radii } from "@proofscan/design-tokens";
import { Pressable, ScrollView, StyleSheet, Text, View, type ViewProps } from "react-native";
import type { ReactNode } from "react";

export const styles = StyleSheet.create({
  screen: { backgroundColor: colors.canvas, flex: 1 },
  layout: { padding: 18, gap: 17, paddingBottom: 42 },
  panel: { backgroundColor: colors.surface, padding: 17, borderRadius: radii.card, borderWidth: 1, borderColor: colors.line, gap: 11 },
  title: { fontSize: 32, lineHeight: 36, fontWeight: "800", letterSpacing: -1.2, color: colors.ink },
  heading: { fontSize: 20, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  text: { fontSize: 15, lineHeight: 23, color: colors.muted },
  input: { borderWidth: 1, borderColor: colors.border, padding: 12, borderRadius: radii.control, minHeight: 48, color: colors.ink, backgroundColor: colors.surface },
  button: { padding: 12, minHeight: 46, borderRadius: radii.control, backgroundColor: colors.brand, justifyContent: "center", alignItems: "center" },
  outline: { backgroundColor: colors.brandTint },
  label: { fontSize: 15, color: "white", fontWeight: "700" },
  outlineLabel: { color: colors.brand },
  error: { color: colors.danger, backgroundColor: colors.dangerTint, padding: 10, borderRadius: radii.control, fontSize: 15, lineHeight: 22 },
  progress: { padding: 8, flexDirection: "row", gap: 4, borderWidth: 1, borderColor: colors.line,
    borderRadius: radii.card, backgroundColor: colors.surface },
  step: { flex: 1, minHeight: 34, alignItems: "center", flexDirection: "row", gap: 4 },
  stepNumber: { width: 21, height: 21, borderRadius: 11, backgroundColor: colors.brandTint, justifyContent: "center", alignItems: "center" },
  stepActive: { backgroundColor: colors.brand },
  stepText: { fontSize: 11, color: colors.muted, fontWeight: "700" },
  stepActiveText: { color: colors.brand },
  stepActiveNumber: { color: colors.surface },
});

export function Screen({ children }: { children: ReactNode }) {
  return <ScrollView style={styles.screen} contentContainerStyle={styles.layout} keyboardShouldPersistTaps="handled">{children}</ScrollView>;
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
  return <View style={styles.progress}>{steps.map((label, index) => <View key={label}
    accessible accessibilityLabel={label + (current === index ? ", current step" : "")} style={styles.step}>
    <View style={[styles.stepNumber, current === index && styles.stepActive]}>
      <Text style={[styles.stepText, current === index && styles.stepActiveNumber]}>{index + 1}</Text>
    </View>
    <Text style={[styles.stepText, current === index && styles.stepActiveText]}>{label}</Text>
  </View>)}</View>;
}
