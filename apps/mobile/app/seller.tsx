import { api, ApiError, type Angle, type DevicePlan, type GuestView, type ScanTicket } from "@proofscan/api-client";
import { colors, radii } from "@proofscan/design-tokens";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Device from "expo-device";
import { fetch as expoFetch } from "expo/fetch";
import { File } from "expo-file-system";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Image, Linking, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { runDeviceTool, type MobileReadings } from "../src/device-tools";
import { apiOrigin, useSession } from "../src/session";
import { Action, Failure, Panel, Screen, StepRail, styles } from "../src/ui";

const angles = ["front", "back", "left", "right"] as const;
const angleLabel: Record<Angle, string> = { front: "Front", back: "Back", left: "Left side", right: "Right side" };
const steps = ["Consent", "Collect", "Review", "Decision"];
const policy = "2026-11-23";

function clean(file: File | null) {
  try { if (file?.exists) file.delete(); } catch { /* Cache files are also cleared by the OS. */ }
}

function sellerFetch(url: string, init: Parameters<typeof expoFetch>[1]) {
  return expoFetch(url, { ...init, credentials: "omit", redirect: "error", signal: init?.signal ?? AbortSignal.timeout(30_000) });
}

export default function Seller() {
  const router = useRouter();
  const client = useQueryClient();
  const session = useSession(state => state.seller);
  const restored = useSession(state => state.restored);
  const restore = useSession(state => state.restore);
  const [restoreError, setRestoreError] = useState<unknown>(null);
  const [ticket, setTicket] = useState<ScanTicket | null>(null);
  const [angle, setAngle] = useState<Angle>("front");
  const [cameraSettingsNeeded, setCameraSettingsNeeded] = useState(false);
  const [cameraSettingsError, setCameraSettingsError] = useState<unknown>(null);
  const [plan, setPlan] = useState<DevicePlan | null>(null);
  const platform = Platform.OS === "ios" ? "ios" : "android";
  const path = "/guest/" + session?.id;
  const key = ["mobile-seller", session?.id];

  useEffect(() => {
    if (!restored) void restore().catch(() => setRestoreError(new Error("Couldn’t restore your session. Open the original seller link again.")));
  }, [restore, restored]);

  function call<T>(suffix: string, data?: unknown) {
    if (!session) return Promise.reject(new Error("Open a private seller link first."));
    return api<T>(path + suffix, data, { origin: apiOrigin(), guestToken: session.guestToken, fetcher: sellerFetch });
  }

  const guest = useQuery({
    queryKey: key, enabled: !!session,
    queryFn: () => call<GuestView>("/exchange", { token: session?.guestToken }),
  });
  const save = (value: GuestView) => client.setQueryData(key, value);
  const consent = useMutation({
    mutationFn: () => call<GuestView>("/consent", { accepted: true, policy_version: policy }),
    onSuccess: save,
  });

  async function scanTicket() {
    if (ticket && Date.parse(ticket.expires_at) > Date.now() + 3000) return ticket;
    const fresh = await call<ScanTicket>("/scan", { platform });
    setTicket(fresh);
    return fresh;
  }

  const photo = useMutation({
    mutationFn: async () => {
      if (!session) throw new Error("Open a private seller link first.");
      setCameraSettingsError(null);
      let permission = await ImagePicker.getCameraPermissionsAsync();
      if (!permission.granted && permission.canAskAgain) permission = await ImagePicker.requestCameraPermissionsAsync();
      setCameraSettingsNeeded(!permission.granted && !permission.canAskAgain);
      if (!permission.granted) throw new Error("Allow camera access to take an exterior photo. You can continue without photos.");
      const captured = await ImagePicker.launchCameraAsync({ mediaTypes: ["images"], quality: 0.8, exif: false });
      if (captured.canceled) return;
      const asset = captured.assets[0];
      const original = new File(asset.uri);
      let processed: File | null = null;
      try {
        const transform = ImageManipulator.manipulate(asset.uri);
        if (Math.max(asset.width, asset.height) > 1280) {
          transform.resize(asset.width >= asset.height ? { width: 1280 } : { height: 1280 });
        }
        const image = await transform.renderAsync();
        const saved = await image.saveAsync({ format: SaveFormat.JPEG, compress: 0.76 });
        processed = new File(saved.uri);
        if (processed.size > 750_000) throw new Error("Try a clearer photo with a plain background.");
        const current = await scanTicket();
        const response = await sellerFetch(apiOrigin() + "/api/v1" + path + "/photos?angle=" + angle, {
          method: "POST",
          headers: { "Content-Type": "image/jpeg", "X-Guest-Token": session.guestToken, "X-Scan-Challenge": current.challenge },
          body: await processed.arrayBuffer(),
        }).catch(() => { throw new Error("Couldn’t upload the photo. Check your connection and try again."); });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail ?? "The photo could not be saved.");
        }
      } finally { clean(processed); clean(original); }
    },
    onSettled: () => client.invalidateQueries({ queryKey: key }),
  });

  async function submitReadings(readings: MobileReadings) {
    if (!readings.model && !readings.memory_gib) throw new Error("This device did not disclose supported hardware readings.");
    const scan = await scanTicket();
    return call<GuestView>("/submit", {
      scan_id: scan.scan_id, challenge: scan.challenge, platform,
      hardware: { ...readings, cpu: [], gpu: [], drives: [] },
    });
  }

  const prepare = useMutation({
    mutationFn: async () => {
      if (!Device.isDevice) throw new Error("Open ProofScan on the device you are selling.");
      await scanTicket();
      return call<DevicePlan>("/agent/plan", { platform });
    },
    onSuccess: setPlan,
  });
  const skipPlan = useMutation({
    mutationFn: (current: DevicePlan) => call<DevicePlan>("/agent/plan/" + current.id, {
      revision: current.revision, action: "skip",
    }),
    onSuccess: () => setPlan(null),
  });
  const submit = useMutation({
    mutationFn: async (approvedPlan: DevicePlan | null) => {
      if (!Device.isDevice) throw new Error("Open ProofScan on the device you are selling.");
      if (!approvedPlan) return submitReadings({
        ...runDeviceTool("model_name").readings,
        ...runDeviceTool("memory_total").readings,
      });
      const planPath = "/agent/plan/" + approvedPlan.id;
      let next = await call<DevicePlan>(planPath, { revision: approvedPlan.revision, action: "approve" });
      const readings: MobileReadings = {};
      for (let count = 0; count < 3 && next.status === "collecting"; count++) {
        if (!next.next_tool) throw new Error("ProofScan did not receive the next device check.");
        const result = runDeviceTool(next.next_tool);
        Object.assign(readings, result.readings);
        next = await call<DevicePlan>(planPath, {
          revision: next.revision, action: "observe", tool: next.next_tool, outcome: result.outcome,
        });
      }
      if (next.status !== "complete") throw new Error("The guided scan did not finish. Start a new plan or use basic collection.");
      return submitReadings(readings);
    },
    onSuccess: save,
    onSettled: () => setPlan(null),
    onError: () => { setTicket(null); void guest.refetch(); },
  });
  const decision = useMutation({
    mutationFn: (value: "share" | "decline") => call<GuestView>("/decision", { decision: value }),
    onSuccess: save,
    onError: () => { void guest.refetch(); },
  });
  const status = guest.data?.verification.status;
  const step = status === "COMPLETED" || status === "DECLINED" ? 3 : status === "SELLER_REVIEW" ? 2
    : status === "CONSENTED" || status === "SCANNING" ? 1 : 0;
  const preview = guest.data?.preview;
  const busy = consent.isPending || photo.isPending || submit.isPending || decision.isPending ||
    prepare.isPending || skipPlan.isPending;
  const collecting = status === "CONSENTED" || status === "SCANNING";
  const linkUnavailable = guest.error instanceof ApiError && guest.error.status === 404;
  const savedAngles = new Set(guest.data?.photos.map(item => item.angle));
  const stageError = status === "SELLER_OPENED" ? consent.error
    : collecting ? submit.error ?? prepare.error ?? skipPlan.error ?? photo.error ?? cameraSettingsError
      : status === "SELLER_REVIEW" ? decision.error : null;

  return <Screen>
    <View style={styles.intro}>
      <Text accessibilityRole="header" style={styles.title}>{guest.data?.verification.label ?? "Your verification"}</Text>
      <Text style={styles.text}>Review your readings and photos before sharing a report.</Text>
    </View>
    {status && !linkUnavailable && <StepRail steps={steps} current={step} />}
    <Failure error={restoreError ?? guest.error ?? stageError} />
    {(!restored || (session && guest.isPending && guest.isFetching)) && <Panel style={sellerStyles.loading}>
      <ActivityIndicator color={colors.brand} />
      <Text accessibilityLiveRegion="polite" style={styles.text}>Opening seller session…</Text>
    </Panel>}
    {guest.isError && !linkUnavailable && <Action quiet disabled={guest.isFetching} onPress={() => void guest.refetch()}>Reconnect</Action>}
    {restored && (!session || linkUnavailable) && <Action onPress={() => router.replace("/scanner")}>Open a seller link</Action>}
    {linkUnavailable && <Text style={styles.text}>Ask your buyer for a fresh seller link.</Text>}
    {!linkUnavailable && <>
    {status === "SELLER_OPENED" && <Panel>
      <Text style={styles.heading}>Review what we collect</Text>
      <Text style={styles.text}>ProofScan reads device model and memory where available. You can add exterior photos, then review everything before the buyer sees it.</Text>
      <Action disabled={busy} onPress={() => consent.mutate()}>{consent.isPending ? "Saving consent…" : "Agree and continue"}</Action>
    </Panel>}
    {collecting && <>
      <Panel>
        <Text accessibilityRole="header" style={styles.heading}>Exterior photos</Text>
        <Text style={styles.text}>Optional. Choose a side and photograph the entire device in even light.</Text>
        <View accessibilityRole="radiogroup" style={sellerStyles.angleGroup}>
          {angles.map(item => {
            const selected = item === angle;
            return <Pressable key={item} accessibilityRole="radio" accessibilityState={{ checked: selected, disabled: busy }}
              disabled={busy} onPress={() => setAngle(item)}
              style={({ pressed }) => [sellerStyles.angle, selected && sellerStyles.angleSelected, pressed && sellerStyles.anglePressed]}>
              <Text style={[styles.fieldLabel, selected && sellerStyles.selectedLabel]}>{angleLabel[item]}</Text>
              {savedAngles.has(item) && <Text style={sellerStyles.saved}>Saved</Text>}
            </Pressable>;
          })}
        </View>
        <Action quiet disabled={busy} onPress={() => { submit.reset(); photo.mutate(); }}>
          {photo.isPending ? "Saving photo…" : savedAngles.has(angle) ? "Retake photo" : "Take photo"}
        </Action>
        {cameraSettingsNeeded && <Action quiet onPress={() => void Linking.openSettings().catch(() => {
          setCameraSettingsError(new Error("Open your phone’s settings and allow camera access for ProofScan."));
        })}>Open camera settings</Action>}
      </Panel>
      <Panel>
        <Text accessibilityRole="header" style={styles.heading}>Device readings</Text>
        <Text style={styles.text}>ProofScan reads the model and memory when available.</Text>
        {plan ? <>
          <Text style={styles.text}>Approve local model and memory checks. If the model name is unavailable, ProofScan may try the operating system’s model code. The planner may send check names and outcomes to Moonshot. You review the actual readings before sharing.</Text>
          <Action disabled={busy} onPress={() => { photo.reset(); submit.mutate(plan); }}>
            {submit.isPending ? "Collecting…" : "Approve checks and collect"}
          </Action>
          <Action quiet disabled={busy} onPress={() => skipPlan.mutate(plan)}>Skip guided checks</Action>
        </> : <>
          <Action disabled={busy} onPress={() => { submit.reset(); prepare.mutate(); }}>
            {prepare.isPending ? "Preparing checks…" : "Plan guided scan"}
          </Action>
          <Action quiet disabled={busy} onPress={() => { photo.reset(); prepare.reset(); skipPlan.reset(); submit.mutate(null); }}>
            {submit.isPending ? "Collecting…" : "Use basic collection"}
          </Action>
        </>}
      </Panel>
    </>}
    {status === "SELLER_REVIEW" && preview && <Panel>
      <Text style={styles.heading}>Review before sharing</Text>
      <Text style={styles.text}>{[preview.hardware.manufacturer, preview.hardware.model].filter(Boolean).join(" ") || "Model unavailable"}</Text>
      <Text style={styles.text}>{preview.hardware.memory_gib ? preview.hardware.memory_gib + " GiB memory" : "Memory unavailable"}</Text>
      {preview.findings.map(item => <Text key={item.metric} style={styles.text}>
        {item.metric} · {item.observed ?? "Unavailable"} · {item.status.toLowerCase()}
      </Text>)}
      {!!preview.visual_evidence?.length && session && <Text style={styles.heading}>Exterior photos</Text>}
      {preview.visual_evidence?.map(item => session ? <Image key={item.id} accessibilityLabel={item.angle + " of device"}
        style={sellerStyles.evidence} resizeMode="contain"
        source={{ uri: apiOrigin() + "/api/v1" + path + "/photos/" + item.id, headers: { "X-Guest-Token": session.guestToken } }} /> : null)}
      <Action disabled={busy} onPress={() => decision.mutate("share")}>{decision.isPending ? "Saving decision…" : "Share signed report"}</Action>
      <Action quiet disabled={busy} onPress={() => decision.mutate("decline")}>Decline to share</Action>
    </Panel>}
    {status === "COMPLETED" && <Panel><Text style={styles.heading}>Report shared</Text><Text style={styles.text}>The buyer can open the signed report in their workspace.</Text></Panel>}
    {status === "DECLINED" && <Panel><Text style={styles.heading}>Sharing declined</Text><Text style={styles.text}>Your readings stayed private.</Text></Panel>}
    {(status === "EXPIRED" || status === "CANCELLED" || status === "FAILED") && <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Verification unavailable</Text>
      <Text style={styles.text}>Ask your buyer for a fresh seller link.</Text>
      <Action quiet onPress={() => router.replace("/scanner")}>Back to device scanner</Action>
    </Panel>}
    </>}
  </Screen>;
}

const sellerStyles = StyleSheet.create({
  loading: { flexDirection: "row", alignItems: "center" },
  angleGroup: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  angle: { flexBasis: "46%", flexGrow: 1, minHeight: 48, justifyContent: "center", padding: 11, borderWidth: 1,
    borderColor: colors.border, borderRadius: radii.control },
  angleSelected: { borderColor: colors.focus, backgroundColor: colors.brandTint },
  selectedLabel: { color: colors.brand },
  anglePressed: { opacity: 0.7 },
  saved: { alignSelf: "flex-start", marginTop: 4, color: colors.mintInk, fontSize: 13, fontWeight: "700" },
  evidence: { height: 185, width: "100%", borderRadius: radii.control, backgroundColor: colors.canvas },
});
