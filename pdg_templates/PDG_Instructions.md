## Basic Instructions to Fill the PDG Sheet

There are some sheets that require special attention.

### WorkSheets in General
- any blue cell header means that the data will not be used in the script, they are mostly notes
- feel free to add columns to the right as needed
- `CableMatrix` sheet will not used in the script
- there are notes in some sheets headers for your reference of accepted values

### Global Core and Access Core Tab
- use these pages to create any global configurations, these should be configurations that do not exist in any other sheets
- Global configurations are deployed to all switches depends on the role
  - "roles" are defined in the `device` sheet
  - only `core` and `access` roles are supported
  - other roles such as `leaf`, `spine` will come soon; contact `peter.zhang@wwt.com` for immediate support

### Banner Tab
Because Banners are very customizable, the same format might not fit every customer especially for the `exec` banner  
Currently the `exec` banner allows you to fill in `Hostname`, `MgmtIP`, `Model` and `SerialNum`. These values are taken from the `Device` tab directly. You can change the format, but don't change the variables and the curly brackets  
Additional variables can be supported but need adjustments to the script. Reach out to `peter.zhang@wwt.com` for support

### VLAN Tab
The VLAN page is strictly for creating VLANs as follows for NX-OS:
```text
vlan 123
  name new_vlan_123
```
Additional columns are for notes purposes only. SVIs will be created in a separate page