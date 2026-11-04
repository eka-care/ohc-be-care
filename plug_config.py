from plugs.manager import PlugManager
from plugs.plug import Plug

abdm = Plug(
    name="abdm",
    package_name="git+https://github.com/ohcnetwork/care-abdm.git",
    version="@main#subdirectory=backend",
)

plugs = [abdm]

manager = PlugManager(plugs)
