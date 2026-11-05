from plugs.manager import PlugManager
from plugs.plug import Plug

care_scribe = Plug(
    name="care_scribe",
    package_name="git+https://github.com/eka-care/care_scribe.git",
    version="@9b32624b511216a928061f2c52793255547e7cee",
)

abdm = Plug(
    name="abdm",
    package_name="git+https://github.com/ohcnetwork/care-abdm.git",
    version="@969a27839c02baeee319de1c07f1f93ef145b959#subdirectory=backend",
)

plugs = [care_scribe, abdm]

manager = PlugManager(plugs)
