# Pan-OS Configuration Snippets


This directory holds all configured configuration snippets. Snippets represent multiple
bits of Pan-OS configuration that should be considered a single entity. Often used to create 'services'
or other related bits of configuration. 


## YAML syntax

Each subdirectory in this directory contain the following:
1. A `metadata.yaml` file that is formatted with using YAML with the following format:

    ```yaml 
    name: snippet_name
    description: snippet description
    extends: gsb_baseline
    variables:
      - name: INF_NAME
        description: Interface Name
        default: Ethernet1/1
        type_hint: text
    snippets:
      - xpath: some/xpath/value/here
        file: filename of xml snippet to load that should exist in this directory
    ```

2. Multiple configuration snippet files. Each should contain a valid XML fragment and may use jinja2 variables.



## Snippet details

Each snippet can define nulitple variables that will be interpolated using the Jinja2 templating language. Each 
variable defined in the `variables` list should define the following:
1. name: The name of the variable found in the snippets
    ```bash
    {{ name }}
    ```
2. description: A brief description of the variable and it's purpose in the configuration
3. label: Human friendly label to display to user
4. extends: Name of another snippet to load 
5. default: A valid default value which will be used if not value is provided by the user
6. type_hint: Used to constrain the types of values accepted. May be implemented by additional third party tools. Examples
are `text`, `ip_address`, `ip_address_with_subnet`, `number`, `enum`


## hints

cd into a snippet dir and run this to find all vars
```bash
grep -r '{{' . |  cut -d'{' -f3 | awk '{ print $1 }' | sort -u

```