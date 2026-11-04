from plugs.manager import PlugManager
from plugs.plug import Plug

care_scribe = Plug(
    name="care_scribe",
    package_name="git+https://github.com/eka-care/care_scribe.git",
    version="@7aec19db4320f49e2fe5f4ce98ef2de9d5666f6d",
)

plugs = [care_scribe]

manager = PlugManager(plugs)
