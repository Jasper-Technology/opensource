# Stage 1: Install DWSIM .deb to extract DLLs
FROM ubuntu:22.04 AS dwsim-install

RUN apt-get update && apt-get install -y --no-install-recommends wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN wget --no-verbose -O /tmp/dwsim.deb \
    "https://github.com/DanWBR/dwsim/releases/download/v9.0.5/dwsim_9.0.5-amd64.deb" \
    && ls -la /tmp/dwsim.deb

RUN dpkg --force-depends -i /tmp/dwsim.deb || true
RUN apt-get update && apt-get install -f -y && rm -rf /var/lib/apt/lists/*
RUN rm /tmp/dwsim.deb

RUN ls /usr/local/lib/dwsim/DWSIM.Automation.dll && echo "DWSIM DLLs verified"

# Stage 2: Build the .NET app
FROM mcr.microsoft.com/dotnet/sdk:8.0-jammy AS build

COPY --from=dwsim-install /usr/local/lib/dwsim /usr/local/lib/dwsim
ENV DWSIM_PATH=/usr/local/lib/dwsim

WORKDIR /src
COPY *.csproj .
RUN dotnet restore
COPY . .
RUN dotnet publish -c Release -o /app

# Stage 3: Runtime — copy our app INTO the DWSIM directory so assembly resolution works
FROM mcr.microsoft.com/dotnet/aspnet:8.0-jammy

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libglib2.0-0 libgtk-3-0 libcairo2 libpango-1.0-0 \
    libgdk-pixbuf2.0-0 libatk1.0-0 \
    fontconfig fonts-dejavu-core \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Copy DWSIM install (the full directory with all DLLs and data files)
COPY --from=dwsim-install /usr/local/lib/dwsim /usr/local/lib/dwsim

# Copy our published app INTO the DWSIM directory (our DLLs + deps alongside DWSIM's)
COPY --from=build /app /usr/local/lib/dwsim

# Run from the DWSIM directory so all assembly resolution works
WORKDIR /usr/local/lib/dwsim

ENV PORT=8000
ENV ASPNETCORE_URLS=http://+:8000
ENV DWSIM_PATH=/usr/local/lib/dwsim
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

# Start without xvfb first — only needed when DWSIM creates flowsheets (GTK/Eto init).
# The web server itself doesn't need it. DWSIM calls can use xvfb-run per-invocation.
ENTRYPOINT ["dotnet", "DwsimBackend.dll"]
