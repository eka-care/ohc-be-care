from plugs.manager import PlugManager
from plugs.plug import Plug

care_scribe = Plug(
    name="care_scribe",
    package_name="git+https://github.com/eka-care/care_scribe.git",
    version="@9b32624b511216a928061f2c52793255547e7cee",
)

plugs = [care_scribe]

manager = PlugManager(plugs)
