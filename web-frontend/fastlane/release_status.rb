# S6: the beta lane writes what it uploaded into docs/ops/release-status.md.
# Plain Ruby (no fastlane actions), so tests/test_release_status.py can run it.
module ReleaseStatus
  PATH = File.expand_path("../../docs/ops/release-status.md", __dir__).freeze

  # Adds one row to the «TestFlight builds» table, which is the last section of the file.
  def self.append_testflight_build(path = PATH, build:, commit:, version:, uploaded_at: Time.now.utc)
    unless File.exist?(path) && File.read(path).include?("## TestFlight builds")
      raise "#{path} has no «TestFlight builds» table"
    end

    stamp = uploaded_at.utc.strftime("%Y-%m-%d %H:%M UTC")
    text = File.read(path)
    text += "\n" unless text.end_with?("\n")
    text += "| #{stamp} | #{version} | #{build} | #{commit} |\n"
    File.write(path, text)
  end
end
