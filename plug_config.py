from plugs.manager import PlugManager
from plugs.plug import Plug

care_scribe = Plug(
    name="care_scribe",
    package_name="git+https://github.com/eka-care/care_scribe.git",
    version="@4bb03093360032c0a8429d142a6578ada303f8cb",
)

plugs = [care_scribe]

manager = PlugManager(plugs)
