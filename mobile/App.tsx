import 'react-native-gesture-handler';
import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { enableScreens } from 'react-native-screens';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { RootNavigator } from './src/navigation/RootNavigator';
import { colors } from './src/ui';
import { clearTokens, loadTokens } from './src/services/authStorage';

enableScreens();

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = React.useState(false);
  const [isHydrating, setIsHydrating] = React.useState(true);

  React.useEffect(() => {
    let isMounted = true;

    const hydrateAuthState = async () => {
      try {
        const tokens = await loadTokens();
        if (isMounted && tokens?.accessToken) {
          setIsAuthenticated(true);
        }
      } finally {
        if (isMounted) {
          setIsHydrating(false);
        }
      }
    };

    hydrateAuthState();

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSignIn = React.useCallback(() => {
    setIsAuthenticated(true);
  }, []);

  const handleSignOut = React.useCallback(async () => {
    try {
      await clearTokens();
    } finally {
      setIsAuthenticated(false);
    }
  }, []);

  return (
    <SafeAreaProvider>
      <StatusBar style="dark" backgroundColor={colors.background} />
      {isHydrating ? (
        <View style={styles.loader}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : (
        <RootNavigator
          isAuthenticated={isAuthenticated}
          onSignIn={handleSignIn}
          onSignOut={handleSignOut}
        />
      )}
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  loader: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.background
  }
});
