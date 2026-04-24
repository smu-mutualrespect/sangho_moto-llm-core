Use this skill when the request depends on strict AWS protocol rendering.

Behavior:
- Respect JSON, REST-JSON, Query/XML, EC2/XML, and REST-XML constraints.
- Never emit prose or commentary in the response fields.
- Preserve core output members needed by the AWS CLI parser.
- If the tool observation suggests protocol risk, choose a simpler response plan with fewer optional fields.
