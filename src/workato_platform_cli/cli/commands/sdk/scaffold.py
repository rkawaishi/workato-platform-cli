"""Connector project scaffold generator."""

from pathlib import Path
from string import Template


CONNECTOR_TEMPLATE = Template("""{
  title: '${title}',

  connection: {
    authorization: {
      type: 'custom_auth'
    },

    base_uri: lambda do |connection|
      ''
    end
  },

  test: lambda do |connection|

  end,

  actions: {

  },

  triggers: {

  },

  methods: {

  },

  object_definitions: {

  },

  pick_lists: {

  }
}
""")

GEMFILE_TEMPLATE = """# frozen_string_literal: true

source 'https://rubygems.org'

gem 'byebug'
gem 'rspec'
gem 'timecop'
gem 'vcr'
gem 'webmock'
gem 'workato-connector-sdk'
"""

RSPEC_TEMPLATE = """--format documentation
--color
--require spec_helper
"""

SPEC_HELPER_TEMPLATE = """# frozen_string_literal: true

require 'workato-connector-sdk'
require 'webmock/rspec'
require 'vcr'

RSpec.configure do |config|
  config.before(:each) do
    Workato::Connector::Sdk::Operation.on_settings_updated = nil
  end
end

WebMock.disable_net_connect!

VCR.configure do |config|
  config.cassette_library_dir = 'tape_library'
  config.hook_into :webmock
end
"""

# Build connector spec as a list to avoid long lines in Python source
_SPEC_LINES = [
    "# frozen_string_literal: true",
    "",
    "RSpec.describe 'connector', :vcr do",
    "  let(:connector) {",
    "    Workato::Connector::Sdk::Connector.from_file(",
    "      'connector.rb', settings",
    "    )",
    "  }",
    "  let(:settings) {",
    "    Workato::Connector::Sdk::Settings.from_default_file",
    "  }",
    "",
    "  it { expect(connector).to be_present }",
    "",
    "  describe 'test' do",
    "    subject(:output) { connector.test(settings) }",
    "",
    "    pending 'add some examples'",
    "  end",
    "end",
    "",
]
CONNECTOR_SPEC_CONTENT = "\n".join(_SPEC_LINES)

SETTINGS_TEMPLATE = """# Add your connector credentials here
# api_key: your_api_key
# api_secret: your_secret
"""

GITIGNORE_TEMPLATE = """master.key
settings.yaml
*.enc
Gemfile.lock
tape_library/
.rspec_status
"""


def generate_scaffold(path: Path, name: str) -> list[str]:
    """Generate a connector project scaffold at the given path.

    Returns a list of created file paths (relative to path).
    """
    title = name.replace("-", " ").replace("_", " ").title()
    created_files: list[str] = []

    # Create directories
    (path / "spec").mkdir(parents=True, exist_ok=True)
    (path / "fixtures" / "actions").mkdir(parents=True, exist_ok=True)
    (path / "fixtures" / "triggers").mkdir(parents=True, exist_ok=True)
    (path / "fixtures" / "methods").mkdir(parents=True, exist_ok=True)
    (path / "tape_library").mkdir(parents=True, exist_ok=True)

    files = {
        "connector.rb": CONNECTOR_TEMPLATE.substitute(title=title),
        "Gemfile": GEMFILE_TEMPLATE,
        ".rspec": RSPEC_TEMPLATE,
        ".gitignore": GITIGNORE_TEMPLATE,
        "settings.yaml": SETTINGS_TEMPLATE,
        "spec/spec_helper.rb": SPEC_HELPER_TEMPLATE,
        "spec/connector_spec.rb": CONNECTOR_SPEC_CONTENT,
    }

    for rel_path, content in files.items():
        file_path = path / rel_path
        file_path.write_text(content)
        created_files.append(rel_path)

    return created_files
