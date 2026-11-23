import java.net.Authenticator;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.PasswordAuthentication;
import java.net.ProxySelector;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class ProxyCheck {
    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " is required");
        return value.trim();
    }

    private static String parseIp(String payload) throws Exception {
        String value = payload.trim();
        Matcher matcher = Pattern.compile("\\\"ip\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"").matcher(value);
        if (matcher.find()) value = matcher.group(1);
        if (!value.matches("[0-9A-Fa-f:.]+")) throw new IllegalArgumentException("Unexpected IP-check response");
        InetAddress.getByName(value);
        return value;
    }

    public static void main(String[] args) throws Exception {
        String profile = System.getenv().getOrDefault("PROXY_PROFILE", "mobile").trim().toLowerCase();
        String prefix = switch (profile) {
            case "mobile" -> "MOBILE_HTTPS_PROXY";
            case "residential" -> "RESIDENTIAL_HTTPS_PROXY";
            default -> throw new IllegalArgumentException("PROXY_PROFILE must be mobile or residential");
        };

        URI proxy = URI.create(required(prefix + "_SERVER"));
        if (!"http".equals(proxy.getScheme()) || proxy.getHost() == null || proxy.getUserInfo() != null) {
            throw new IllegalArgumentException(prefix + "_SERVER must be a credential-free http:// endpoint");
        }
        int port = proxy.getPort() == -1 ? 80 : proxy.getPort();
        String username = required(prefix + "_USERNAME");
        char[] password = required(prefix + "_PASSWORD").toCharArray();

        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(30))
                .proxy(ProxySelector.of(new InetSocketAddress(proxy.getHost(), port)))
                .authenticator(new Authenticator() {
                    @Override
                    protected PasswordAuthentication getPasswordAuthentication() {
                        return getRequestorType() == RequestorType.PROXY
                                ? new PasswordAuthentication(username, password)
                                : null;
                    }
                })
                .build();

        URI check = URI.create(System.getenv().getOrDefault("IP_CHECK_URL", "https://api.ipify.org?format=json"));
        HttpRequest request = HttpRequest.newBuilder(check).timeout(Duration.ofSeconds(30)).GET().build();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() > 299) {
            throw new IllegalStateException("IP check returned HTTP " + response.statusCode());
        }
        System.out.printf("Profile: %s%nProxy: %s%nExit IP: %s%n", profile, proxy, parseIp(response.body()));
    }
}
