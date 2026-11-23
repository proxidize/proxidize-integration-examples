require 'ipaddr'
require 'json'
require 'net/http'
require 'uri'

def required(name)
  value = ENV[name]&.strip
  raise ArgumentError, "#{name} is required" if value.nil? || value.empty?
  value
end

profile = ENV.fetch('PROXY_PROFILE', 'mobile').strip.downcase
prefix = { 'mobile' => 'MOBILE_HTTPS_PROXY', 'residential' => 'RESIDENTIAL_HTTPS_PROXY' }[profile]
raise ArgumentError, 'PROXY_PROFILE must be mobile or residential' unless prefix

proxy = URI(required("#{prefix}_SERVER"))
unless proxy.scheme == 'http' && proxy.host && proxy.userinfo.nil?
  raise ArgumentError, "#{prefix}_SERVER must be a credential-free http:// endpoint"
end

target = URI(ENV.fetch('IP_CHECK_URL', 'https://api.ipify.org?format=json'))
client = Net::HTTP::Proxy(
  proxy.host,
  proxy.port,
  required("#{prefix}_USERNAME"),
  required("#{prefix}_PASSWORD")
).new(target.host, target.port)
client.use_ssl = target.scheme == 'https'
client.open_timeout = 30
client.read_timeout = 30

response = client.start { |http| http.request(Net::HTTP::Get.new(target)) }
response.value
payload = response.body.strip
ip = JSON.parse(payload).fetch('ip', payload)
IPAddr.new(ip)

puts "Profile: #{profile}"
puts "Proxy: #{proxy}"
puts "Exit IP: #{ip}"
