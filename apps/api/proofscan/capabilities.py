from pydantic import BaseModel


class Capability(BaseModel):
    internal_snapshot: bool
    battery_health: bool
    storage_capacity: bool
    external_visual_scan: bool
    hardware_attestation: bool = False


CAPABILITIES = {
    "windows": Capability(
        internal_snapshot=True, battery_health=True, storage_capacity=True, external_visual_scan=True
    ),
    "android": Capability(
        internal_snapshot=True, battery_health=False, storage_capacity=False, external_visual_scan=True
    ),
    "ios": Capability(
        internal_snapshot=True, battery_health=False, storage_capacity=False, external_visual_scan=True
    ),
    "simulator": Capability(
        internal_snapshot=False, battery_health=False, storage_capacity=False, external_visual_scan=False
    ),
    "web": Capability(
        internal_snapshot=False, battery_health=False, storage_capacity=False, external_visual_scan=True
    ),
    "macos": Capability(
        internal_snapshot=True, battery_health=False, storage_capacity=False, external_visual_scan=True
    ),
}
